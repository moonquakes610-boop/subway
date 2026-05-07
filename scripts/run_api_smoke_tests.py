"""
API 冒烟测试（不依赖外部服务进程）：
- 使用 Flask test_client 直接验证核心接口可用性
- 覆盖登录、规划、反馈、管理员查询、CSRF 校验

运行：
    py -3 scripts/run_api_smoke_tests.py
"""

from __future__ import annotations

import os
import random
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

# 让本次测试创建的 smoke_admin 用户具备管理员权限
os.environ["BSG_ADMIN_USERS"] = "admin,smoke_admin"

from api_server import app


def _rand_suffix(n: int = 6) -> str:
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choice(chars) for _ in range(n))


def _must(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _json(resp):
    return resp.get_json(silent=True) or {}


def _register(client, username: str, password: str) -> None:
    r = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": password,
            "password_confirm": password,
        },
    )
    data = _json(r)
    _must(r.status_code == 200 and data.get("ok") is True, f"注册失败: {r.status_code} {data}")


def _login(client, username: str, password: str) -> str:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    data = _json(r)
    _must(r.status_code == 200 and data.get("ok") is True, f"登录失败: {r.status_code} {data}")
    token = str(data.get("csrf_token") or "")
    _must(bool(token), "登录响应缺少 csrf_token")
    return token


def main() -> int:
    with app.test_client() as client:
        # 1) 健康检查
        r = client.get("/api/health")
        _must(r.status_code == 200 and _json(r).get("ok") is True, "健康检查失败")

        # 2) 普通用户流程
        user = f"smoke_user_{_rand_suffix()}"
        pwd = "Smoke123!"
        _register(client, user, pwd)
        csrf = _login(client, user, pwd)

        # 2.1 CSRF 校验应生效（缺 token 时应失败）
        r = client.post(
            "/api/feedback",
            json={"issue_type": "other", "severity": "low", "content": "csrf check fail expected", "reproducible": False},
        )
        _must(r.status_code == 403, f"CSRF 未生效，期望403，实际 {r.status_code}")

        # 2.2 路线查询（带 token）
        r = client.post(
            "/api/plan",
            headers={"X-CSRF-Token": csrf},
            json={
                "from": "西单",
                "to": "圆明园",
                "strategy": "compare",
                "guide_mode": "commute",
            },
        )
        d = _json(r)
        _must(r.status_code == 200 and d.get("ok") is True and d.get("plan"), f"路线查询失败: {r.status_code} {d}")

        # 2.3 提交反馈（带 token）
        r = client.post(
            "/api/feedback",
            headers={"X-CSRF-Token": csrf},
            json={
                "issue_type": "route_bad",
                "severity": "medium",
                "content": "冒烟测试：路线建议可读性还可以优化。",
                "reproducible": True,
                "from_station": "西单",
                "to_station": "圆明园",
                "strategy": "compare",
            },
        )
        d = _json(r)
        _must(r.status_code == 200 and d.get("ok") is True, f"反馈提交失败: {r.status_code} {d}")

        r = client.get("/api/feedback/my?limit=5")
        d = _json(r)
        _must(r.status_code == 200 and d.get("ok") is True and isinstance(d.get("items"), list), "我的反馈查询失败")

        r = client.post(
            "/api/reference/prohibited-check",
            headers={"X-CSRF-Token": csrf},
            json={"q": "打火机"},
        )
        d = _json(r)
        _must(
            r.status_code == 200
            and d.get("ok") is True
            and d.get("data", {}).get("verdict") == "likely_prohibited",
            f"携带物品查询失败: {r.status_code} {d}",
        )

        # 3) 管理员流程
        client.get("/api/auth/logout")
        admin_user = "smoke_admin"
        admin_pwd = "Smoke123!"
        # 多次运行时可能已存在，存在则忽略注册错误
        reg = client.post(
            "/api/auth/register",
            json={
                "username": admin_user,
                "password": admin_pwd,
                "password_confirm": admin_pwd,
            },
        )
        if reg.status_code != 200:
            # 允许“已存在”继续
            msg = str((_json(reg).get("error") or ""))
            _must("已被注册" in msg, f"管理员注册异常: {reg.status_code} {_json(reg)}")
        admin_csrf = _login(client, admin_user, admin_pwd)

        for path in (
            "/api/admin/summary",
            "/api/admin/feedback/stats",
            "/api/admin/feedback/trend?days=7",
            "/api/admin/feedback?limit=10&status=all",
            "/api/admin/feedback/export.csv?status=all",
        ):
            rr = client.get(path)
            _must(rr.status_code == 200, f"管理员接口失败: {path} -> {rr.status_code}")

        # 管理员更新一条反馈状态（若有）
        rr = client.get("/api/admin/feedback?limit=1&status=all")
        items = _json(rr).get("items") or []
        if items:
            fid = int(items[0]["id"])
            upd = client.patch(
                f"/api/admin/feedback/{fid}",
                headers={"X-CSRF-Token": admin_csrf},
                json={"status": "in_progress", "resolution_note": "冒烟测试更新"},
            )
            _must(upd.status_code == 200 and _json(upd).get("ok") is True, f"反馈状态更新失败: {upd.status_code}")

    print("API 冒烟测试通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

