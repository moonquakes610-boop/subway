"""
北京地铁出行指南 — HTTP 服务（静态页 + 鉴权 API）。

启动（项目根目录）：
    pip install -r requirements.txt
    py -3 scripts/init_auth_db.py
    py -3 scripts/seed_demo_user.py
    py -3 api_server.py

访问：http://127.0.0.1:8765/  （首页；核心功能需登录）
环境变量：BSG_SECRET_KEY（生产必设）、BSG_HOST、BSG_PORT
"""

from __future__ import annotations

import os
import secrets
import sys
import traceback
from datetime import timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import quote

# 兼容部分 Windows 便携 Python：默认 sys.path 不含 site-packages。
_py_dir = Path(sys.executable).resolve().parent
_site_candidates = [
    _py_dir / "Lib" / "site-packages",
    _py_dir.parent / "Lib" / "site-packages",
    Path(sys.prefix) / "Lib" / "site-packages",
]
for _p in _site_candidates:
    if _p.exists():
        _s = str(_p)
        if _s not in sys.path:
            sys.path.append(_s)

from flask import Flask, Response, jsonify, redirect, request, session

# 项目根
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.auth_db import (
    admin_feedback_daily,
    admin_feedback_stats,
    admin_list_feedback,
    admin_list_users,
    admin_update_user_role,
    admin_recent_history,
    admin_summary,
    admin_update_feedback_status,
    create_user,
    get_user_by_id,
    get_user_by_username,
    insert_feedback,
    is_admin_user,
    insert_query_history,
    list_feedback_by_user,
    list_history,
)
from src.auth_passwords import hash_password, verify_password
from src.auth_policy import PolicyError, validate_register_passwords, validate_username
from src.auth_rate_limit import check_locked, clear_fails, record_fail
from src.errors import SubwayGuideError
from src.logutil import setup_logging
from src.reference_data import (
    batch_station_accessibility,
    load_passenger_rules,
    load_prohibited_items,
    load_runtime_status,
    load_station_accessibility_raw,
)
from src.web_service import query_route, subway_error_message

import logging
import csv
import io

setup_logging(logging.INFO)

app = Flask(__name__, static_folder="frontend", static_url_path="")
app.config["SECRET_KEY"] = os.environ.get("BSG_SECRET_KEY") or "dev-insecure-change-me"
if app.config["SECRET_KEY"] == "dev-insecure-change-me":
    print(
        "[警告] 未设置 BSG_SECRET_KEY，生产环境极不安全。",
        flush=True,
    )
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=1)
# 生产 HTTPS 时改为 True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("BSG_HTTPS", "").lower() in (
    "1",
    "true",
    "yes",
)

log = logging.getLogger(__name__)
ISSUE_TYPE_LABELS = {
    "route_bad": "路线不合理",
    "station_outdated": "站点信息过时",
    "a11y_error": "无障碍信息错误",
    "other": "其他",
}
SEVERITY_LABELS = {"high": "高", "medium": "中", "low": "低"}
ALLOWED_AVATARS = {"🙂", "😎", "🧑‍💻", "🚇", "🧭", "🌟", "🐼", "🦊"}


def _json_err(msg: str, code: int = 400, extra: dict | None = None):
    body: dict = {"ok": False, "error": msg}
    if extra:
        body.update(extra)
    return jsonify(body), code


def _ensure_csrf_token() -> str:
    tok = str(session.get("csrf_token") or "")
    if not tok:
        tok = secrets.token_urlsafe(24)
        session["csrf_token"] = tok
    return tok


def _csrf_exempt(path: str) -> bool:
    return path in (
        "/api/auth/login",
        "/api/auth/register",
        "/api/health",
        "/api/auth/csrf",
    )


@app.before_request
def _enforce_csrf():
    if not request.path.startswith("/api/"):
        return None
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    if _csrf_exempt(request.path):
        return None
    if not session.get("user_id"):
        return None
    sent = request.headers.get("X-CSRF-Token") or ""
    expected = str(session.get("csrf_token") or "")
    if not expected or sent != expected:
        return _json_err("CSRF 校验失败，请刷新页面后重试。", 403, {"code": "csrf_failed"})
    return None


def _login_rl_key() -> str:
    data = request.get_json(silent=True) or {}
    u = (data.get("username") or "").strip().lower()
    return f"{request.remote_addr}:{u}"


def require_auth(f):
    @wraps(f)
    def wrapped(*a, **kw):
        uid = session.get("user_id")
        if not uid:
            return _json_err("需要登录后使用", 401, {"code": "auth_required"})
        u = get_user_by_id(int(uid))
        if not u:
            session.clear()
            return _json_err("会话已失效，请重新登录", 401, {"code": "auth_required"})
        return f(*a, current_user=u, **kw)

    return wrapped


def require_admin(f):
    @wraps(f)
    def wrapped(*a, **kw):
        uid = session.get("user_id")
        if not uid:
            return _json_err("需要登录后使用", 401, {"code": "auth_required"})
        u = get_user_by_id(int(uid))
        if not u:
            session.clear()
            return _json_err("会话已失效，请重新登录", 401, {"code": "auth_required"})
        if not is_admin_user(u):
            return _json_err("需要管理员权限", 403, {"code": "admin_required"})
        return f(*a, current_user=u, **kw)

    return wrapped


# ----- 页面路由（同端口，保证 Cookie 会话）


@app.route("/")
def page_home():
    return app.send_static_file("home.html")


@app.route("/index.html")
def page_index_redirect():
    return redirect("/", 302)


@app.route("/app")
@app.route("/app.html")
def page_app():
    uid = session.get("user_id")
    if not uid or not get_user_by_id(int(uid)):
        session.clear()
        return redirect(f"/login.html?next={quote('/app.html')}", 302)
    return app.send_static_file("app.html")


@app.route("/login")
@app.route("/login.html")
def page_login():
    return app.send_static_file("login.html")


@app.route("/register")
@app.route("/register.html")
def page_register():
    return app.send_static_file("register.html")


@app.route("/profile")
@app.route("/profile.html")
def page_profile():
    uid = session.get("user_id")
    if not uid or not get_user_by_id(int(uid)):
        session.clear()
        return redirect(f"/login.html?next={quote('/profile.html')}", 302)
    return app.send_static_file("profile.html")


@app.route("/admin")
@app.route("/admin.html")
def page_admin():
    uid = session.get("user_id")
    if not uid:
        return redirect(f"/login.html?next={quote('/admin.html')}", 302)
    u = get_user_by_id(int(uid))
    if not is_admin_user(u):
        return redirect("/app.html", 302)
    return app.send_static_file("admin.html")


# 直接访问静态资源（/css/ /js/）由 Flask 默认 static 提供


# ----- 健康检查（可匿名）


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify(
        {
            "ok": True,
            "service": "beijing-subway-guide",
            "auth": "session",
        }
    )


# ----- 鉴权


@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json(silent=True) or {}
    avatar = str(data.get("avatar") or "🙂")
    requested_role = str(data.get("role") or "passenger").strip().lower()
    if requested_role not in ("admin", "passenger"):
        requested_role = "passenger"
    if avatar not in ALLOWED_AVATARS:
        avatar = "🙂"
    try:
        username = validate_username((data.get("username") or ""))
        p1 = data.get("password") or ""
        p2 = data.get("password_confirm") or data.get("confirm") or ""
        validate_register_passwords(p1, p2)
    except PolicyError as e:
        return _json_err(str(e), 400)

    if get_user_by_username(username):
        return _json_err("该用户名已被注册，请更换用户名。", 400)

    try:
        uid = create_user(username, hash_password(p1), avatar=avatar, requested_role=requested_role)
    except Exception as e:
        log.error("register db: %s", e)
        if "UNIQUE" in str(e) or "unique" in str(e).lower():
            return _json_err("该用户名已被注册，请更换用户名。", 400)
        return _json_err("注册失败，请稍后再试。", 500)
    return jsonify(
        {
            "ok": True,
            "user_id": uid,
            "username": username,
            "avatar": avatar,
            "role": requested_role,
        }
    )


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    remember = bool(data.get("remember") or data.get("remember_me"))

    rl_key = f"{request.remote_addr}:{username.lower()}" if username else f"{request.remote_addr}:"
    locked = check_locked(rl_key)
    if locked:
        return _json_err(locked, 429)

    row = get_user_by_username(username)
    ok_login = bool(row) and verify_password(password, str(row.get("password_hash", "")))
    if not ok_login:
        extra = record_fail(rl_key)
        if extra:
            return _json_err(extra, 429)
        return _json_err("用户名或密码错误，请检查后重试。", 401)

    clear_fails(rl_key)
    session["user_id"] = int(row["id"])
    session["username"] = str(row["username"])
    session.permanent = remember
    if remember:
        app.permanent_session_lifetime = timedelta(days=30)
    else:
        app.permanent_session_lifetime = timedelta(days=1)
    csrf_token = _ensure_csrf_token()
    return jsonify(
        {
            "ok": True,
            "csrf_token": csrf_token,
            "user": {
                "id": row["id"],
                "username": row["username"],
                "role": row.get("role") or ("admin" if is_admin_user(row) else "passenger"),
                "avatar": row.get("avatar") or "🙂",
                "created_at": row.get("created_at"),
            },
        }
    )


@app.route("/api/auth/logout", methods=["POST", "GET"])
def auth_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/auth/csrf", methods=["GET"])
def auth_csrf():
    return jsonify({"ok": True, "csrf_token": _ensure_csrf_token()})


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    uid = session.get("user_id")
    if not uid:
        return _json_err("未登录", 401, {"code": "auth_required"})
    u = get_user_by_id(int(uid))
    if not u:
        session.clear()
        return _json_err("未登录", 401, {"code": "auth_required"})
    return jsonify(
        {
            "ok": True,
            "user": {
                "id": u["id"],
                "username": u["username"],
                "role": u.get("role") or ("admin" if is_admin_user(u) else "passenger"),
                "avatar": u.get("avatar") or "🙂",
                "created_at": u.get("created_at"),
                "is_admin": is_admin_user(u),
            },
            "csrf_token": _ensure_csrf_token(),
        }
    )


@app.route("/api/history", methods=["GET"])
@require_auth
def history_list(current_user: dict, **__):
    limit = int(request.args.get("limit", 20))
    rows = list_history(int(current_user["id"]), limit=limit)
    return jsonify({"ok": True, "items": rows})


@app.route("/api/feedback", methods=["POST"])
@require_auth
def feedback_submit(current_user: dict, **__):
    data = request.get_json(silent=True) or {}
    issue_type = str(data.get("issue_type") or "").strip()
    content = str(data.get("content") or "").strip()
    reproducible = bool(data.get("reproducible"))
    severity = str(data.get("severity") or "medium").strip().lower()
    if issue_type not in ("route_bad", "station_outdated", "a11y_error", "other"):
        return _json_err("issue_type 无效。", 400)
    if severity not in ("high", "medium", "low"):
        return _json_err("severity 无效，需为 high/medium/low。", 400)
    if len(content) < 6:
        return _json_err("反馈内容过短，请至少输入 6 个字符。", 400)
    if len(content) > 1000:
        return _json_err("反馈内容过长，请控制在 1000 字以内。", 400)
    fid = insert_feedback(
        int(current_user["id"]),
        issue_type=issue_type,
        content=content,
        reproducible=reproducible,
        severity=severity,
        from_station=str(data.get("from_station") or "").strip() or None,
        to_station=str(data.get("to_station") or "").strip() or None,
        strategy=str(data.get("strategy") or "").strip() or None,
        contact=str(data.get("contact") or "").strip() or None,
    )
    return jsonify({"ok": True, "feedback_id": fid})


@app.route("/api/feedback/my", methods=["GET"])
@require_auth
def feedback_my(current_user: dict, **__):
    limit = int(request.args.get("limit", 30))
    rows = list_feedback_by_user(int(current_user["id"]), limit=limit)
    return jsonify({"ok": True, "items": rows})


# ----- 受保护：路线与参考数据


@app.route("/api/plan", methods=["GET", "POST"])
@require_auth
def plan(current_user, **__):
    def _parse_query_time_minutes(raw: str | None) -> int | None:
        if not raw or not str(raw).strip():
            return None
        s = str(raw).strip().replace("：", ":")
        parts = s.split(":")
        if len(parts) != 2:
            return None
        try:
            h, m = int(parts[0]), int(parts[1])
            if h < 0 or h > 23 or m < 0 or m > 59:
                return None
            return h * 60 + m
        except ValueError:
            return None

    if request.method == "POST" and request.is_json:
        data = request.get_json(silent=True) or {}
        frm = (data.get("from") or data.get("frm") or "").strip()
        to = (data.get("to") or "").strip()
        strategy = (data.get("strategy") or "min_time").strip().lower()
        guide_mode = (data.get("guide_mode") or "commute").strip().lower()
        qtm = _parse_query_time_minutes(
            str(data.get("query_time") or data.get("client_time") or "")
        )
    else:
        frm = (request.args.get("from") or request.args.get("frm") or "").strip()
        to = (request.args.get("to") or "").strip()
        strategy = (request.args.get("strategy") or "min_time").strip().lower()
        guide_mode = (request.args.get("guide_mode") or "commute").strip().lower()
        qtm = _parse_query_time_minutes(request.args.get("query_time") or request.args.get("t"))

    if strategy not in ("min_time", "min_transfer", "compare"):
        return _json_err("参数 strategy 须为 min_time、min_transfer 或 compare。", 400)
    if guide_mode not in ("commute", "tour", "senior", "rush"):
        return _json_err("参数 guide_mode 须为 commute、tour、senior 或 rush。", 400)
    if not frm or not to:
        return _json_err("请提供起点 from 与终点 to。", 400)
    rebuild = request.args.get("rebuild", "").lower() in ("1", "true", "yes")
    try:
        payload = query_route(
            frm,
            to,
            strategy,
            guide_mode=guide_mode,
            force_rebuild_cache=rebuild,
            query_time_minutes=qtm,
        )
    except SubwayGuideError as e:
        return _json_err(str(e), 400)
    except Exception as e:
        return _json_err(subway_error_message(e), 500)
    p = payload.get("plan")
    if p and current_user:
        try:
            insert_query_history(
                int(current_user["id"]),
                from_station=frm,
                to_station=to,
                strategy=strategy,
                total_time_minutes=p.get("total_time_minutes_rounded"),
                transfer_count=p.get("transfer_count"),
                estimated_fare_yuan=p.get("estimated_fare_yuan"),
            )
        except Exception as e:
            log.warning("history save skipped: %s", e)
    return jsonify(payload)


@app.route("/api/reference/passenger-rules", methods=["GET"])
@require_auth
def reference_passenger_rules(current_user, **__):
    return jsonify({"ok": True, "data": load_passenger_rules()})


@app.route("/api/reference/prohibited-items", methods=["GET"])
@require_auth
def reference_prohibited(current_user, **__):
    return jsonify({"ok": True, "data": load_prohibited_items()})


@app.route("/api/reference/station-accessibility-meta", methods=["GET"])
@require_auth
def reference_a11y_meta(current_user, **__):
    raw = load_station_accessibility_raw()
    return jsonify(
        {
            "ok": True,
            "data": {
                "version": raw.get("version"),
                "meta": raw.get("meta") or {},
            },
        }
    )


@app.route("/api/runtime/status", methods=["GET"])
@require_auth
def runtime_status(current_user, **__):
    return jsonify({"ok": True, "data": load_runtime_status()})


@app.route("/api/accessibility/batch", methods=["POST"])
@require_auth
def accessibility_batch(current_user, **__):
    body = request.get_json(silent=True) or {}
    names = body.get("stations")
    if not isinstance(names, list):
        return _json_err("请提供 JSON 数组 stations。", 400)
    str_names = [str(n).strip() for n in names if str(n).strip()]
    seen: set[str] = set()
    ordered: list[str] = []
    for n in str_names:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return jsonify(batch_station_accessibility(ordered))


@app.route("/api/admin/summary", methods=["GET"])
@require_admin
def admin_api_summary(current_user, **__):
    return jsonify({"ok": True, "data": admin_summary()})


@app.route("/api/admin/users", methods=["GET"])
@require_admin
def admin_api_users(current_user, **__):
    limit = int(request.args.get("limit", 100))
    return jsonify({"ok": True, "items": admin_list_users(limit=limit)})


@app.route("/api/admin/users/<int:user_id>/role", methods=["PATCH"])
@require_admin
def admin_api_user_role_update(user_id: int, current_user, **__):
    data = request.get_json(silent=True) or {}
    role = (data.get("role") or "").strip().lower()
    if role not in ("admin", "passenger"):
        return _json_err("role 仅支持 admin 或 passenger", 400)
    if int(current_user["id"]) == user_id and role != "admin":
        return _json_err("不能将当前登录管理员降级为 passenger。", 400)
    ok = admin_update_user_role(user_id, role)
    if not ok:
        return _json_err("用户不存在或更新失败。", 404)
    return jsonify({"ok": True})


@app.route("/api/admin/history", methods=["GET"])
@require_admin
def admin_api_history(current_user, **__):
    limit = int(request.args.get("limit", 100))
    return jsonify({"ok": True, "items": admin_recent_history(limit=limit)})


@app.route("/api/admin/feedback", methods=["GET"])
@require_admin
def admin_api_feedback(current_user, **__):
    limit = int(request.args.get("limit", 200))
    status = (request.args.get("status") or "all").strip().lower()
    issue_type = (request.args.get("issue_type") or "all").strip().lower()
    from_date = (request.args.get("from_date") or "").strip() or None
    to_date = (request.args.get("to_date") or "").strip() or None
    if status not in ("all", "pending", "in_progress", "resolved"):
        return _json_err("status 仅支持 all/pending/in_progress/resolved", 400)
    if issue_type not in ("all", "route_bad", "station_outdated", "a11y_error", "other"):
        return _json_err("issue_type 无效", 400)
    return jsonify(
        {
            "ok": True,
            "items": admin_list_feedback(
                limit=limit,
                status=status,
                issue_type=issue_type,
                from_date=from_date,
                to_date=to_date,
            ),
        }
    )


@app.route("/api/admin/feedback/stats", methods=["GET"])
@require_admin
def admin_api_feedback_stats(current_user, **__):
    return jsonify({"ok": True, "data": admin_feedback_stats()})


@app.route("/api/admin/feedback/trend", methods=["GET"])
@require_admin
def admin_api_feedback_trend(current_user, **__):
    days = int(request.args.get("days", 7))
    return jsonify({"ok": True, "items": admin_feedback_daily(days=days)})


@app.route("/api/admin/feedback/export.csv", methods=["GET"])
@require_admin
def admin_api_feedback_export(current_user, **__):
    status = (request.args.get("status") or "all").strip().lower()
    issue_type = (request.args.get("issue_type") or "all").strip().lower()
    from_date = (request.args.get("from_date") or "").strip() or None
    to_date = (request.args.get("to_date") or "").strip() or None
    if status not in ("all", "pending", "in_progress", "resolved"):
        return _json_err("status 仅支持 all/pending/in_progress/resolved", 400)
    if issue_type not in ("all", "route_bad", "station_outdated", "a11y_error", "other"):
        return _json_err("issue_type 无效", 400)
    items = admin_list_feedback(
        limit=1000,
        status=status,
        issue_type=issue_type,
        from_date=from_date,
        to_date=to_date,
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "ID",
            "用户",
            "时间",
            "问题类型",
            "严重程度",
            "状态",
            "起点",
            "终点",
            "策略",
            "描述",
            "处理备注",
            "联系方式",
        ]
    )
    for it in items:
        writer.writerow(
            [
                it.get("id"),
                it.get("username") or "",
                it.get("created_at") or "",
                ISSUE_TYPE_LABELS.get(str(it.get("issue_type") or ""), str(it.get("issue_type") or "")),
                SEVERITY_LABELS.get(str(it.get("severity") or ""), str(it.get("severity") or "")),
                str(it.get("status") or ""),
                it.get("from_station") or "",
                it.get("to_station") or "",
                it.get("strategy") or "",
                it.get("content") or "",
                it.get("resolution_note") or "",
                it.get("contact") or "",
            ]
        )
    csv_text = "\ufeff" + buf.getvalue()
    return Response(
        csv_text,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=feedback_export.csv"},
    )


@app.route("/api/admin/feedback/<int:feedback_id>", methods=["PATCH"])
@require_admin
def admin_api_feedback_update(feedback_id: int, current_user, **__):
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip().lower()
    if status not in ("pending", "in_progress", "resolved"):
        return _json_err("status 仅支持 pending/in_progress/resolved", 400)
    note = str(data.get("resolution_note") or "")
    ok = admin_update_feedback_status(feedback_id, status=status, resolution_note=note)
    if not ok:
        return _json_err("反馈记录不存在。", 404)
    return jsonify({"ok": True})


def main() -> int:
    from src import auth_db

    auth_db.ensure_db()
    host = os.environ.get("BSG_HOST", "127.0.0.1")
    port = int(os.environ.get("BSG_PORT", "8765"))
    print("── 北京地铁出行指南 ──", flush=True)
    print(f"  打开首页：http://{host}:{port}/", flush=True)
    print(f"  核心功能：http://{host}:{port}/app.html  （需登录）", flush=True)
    app.run(host=host, port=port, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
