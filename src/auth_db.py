"""SQLite 持久化：用户与查询历史。"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "auth" / "app.db"
SCHEMA_PATH = ROOT / "data" / "auth" / "init_schema.sql"


_db_initialized = False
ADMIN_USERNAMES = frozenset(
    x.strip().lower()
    for x in os.environ.get("BSG_ADMIN_USERS", "admin").split(",")
    if x.strip()
)


def ensure_db() -> None:
    global _db_initialized
    if _db_initialized and DB_PATH.is_file():
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        if SCHEMA_PATH.is_file():
            with SCHEMA_PATH.open("r", encoding="utf-8") as f:
                conn.executescript(f.read())
        # 兼容旧库：补 users.role 列（若已存在会抛错，忽略即可）。
        try:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'passenger'")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN avatar TEXT NOT NULL DEFAULT '🙂'")
        except sqlite3.OperationalError:
            pass
        # 兼容旧库：补 feedback.severity 列（若已存在会抛错，忽略即可）。
        try:
            conn.execute("ALTER TABLE feedback ADD COLUMN severity TEXT NOT NULL DEFAULT 'medium'")
        except sqlite3.OperationalError:
            pass
        # 同步白名单管理员角色，便于从用户名白名单平滑过渡到 role 模型。
        if ADMIN_USERNAMES:
            placeholders = ",".join("?" for _ in ADMIN_USERNAMES)
            conn.execute(
                f"UPDATE users SET role = 'admin' WHERE lower(username) IN ({placeholders})",
                tuple(ADMIN_USERNAMES),
            )
        conn.commit()
    _db_initialized = True


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def get_user_by_username(username: str) -> dict[str, Any] | None:
    u = (username or "").strip()
    if not u:
        return None
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT id, username, role, avatar, password_hash, created_at FROM users WHERE username = ?",
            (u,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT id, username, role, avatar, created_at FROM users WHERE id = ?",
            (user_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def create_user(
    username: str, password_hash: str, avatar: str = "🙂", requested_role: str | None = None
) -> int:
    uname = username.strip()
    role_req = str(requested_role or "").strip().lower()
    if role_req in ("admin", "passenger"):
        role = role_req
    else:
        role = "admin" if is_admin_username(uname) else "passenger"
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, role, avatar, password_hash) VALUES (?, ?, ?, ?)",
            (uname, role, (avatar or "🙂"), password_hash),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def is_admin_username(username: str) -> bool:
    return (username or "").strip().lower() in ADMIN_USERNAMES


def is_admin_user(user: dict[str, Any] | None) -> bool:
    if not user:
        return False
    if str(user.get("role") or "").strip().lower() == "admin":
        return True
    return is_admin_username(str(user.get("username") or ""))


def insert_query_history(
    user_id: int,
    *,
    from_station: str,
    to_station: str,
    strategy: str,
    total_time_minutes: float | None,
    transfer_count: int | None,
    estimated_fare_yuan: int | None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO query_history
              (user_id, from_station, to_station, strategy, total_time_minutes,
               transfer_count, estimated_fare_yuan)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                from_station,
                to_station,
                strategy,
                total_time_minutes,
                transfer_count,
                estimated_fare_yuan,
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def list_history(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    limit = max(1, min(100, int(limit)))
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT id, from_station, to_station, strategy, total_time_minutes,
                   transfer_count, estimated_fare_yuan, created_at
            FROM query_history
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def admin_list_users(limit: int = 200) -> list[dict[str, Any]]:
    limit = max(1, min(500, int(limit)))
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT
              u.id,
              u.username,
              u.role,
              u.created_at,
              COUNT(q.id) AS query_count,
              MAX(q.created_at) AS last_query_at
            FROM users u
            LEFT JOIN query_history q ON q.user_id = u.id
            GROUP BY u.id, u.username, u.created_at
            ORDER BY u.created_at DESC, u.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]


def admin_update_user_role(user_id: int, role: str) -> bool:
    role_norm = (role or "").strip().lower()
    if role_norm not in ("admin", "passenger"):
        return False
    with get_conn() as conn:
        cur = conn.execute("UPDATE users SET role = ? WHERE id = ?", (role_norm, user_id))
        conn.commit()
        return (cur.rowcount or 0) > 0


def admin_recent_history(limit: int = 200) -> list[dict[str, Any]]:
    limit = max(1, min(500, int(limit)))
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT
              q.id,
              u.username,
              q.from_station,
              q.to_station,
              q.strategy,
              q.total_time_minutes,
              q.transfer_count,
              q.estimated_fare_yuan,
              q.created_at
            FROM query_history q
            JOIN users u ON u.id = q.user_id
            ORDER BY q.created_at DESC, q.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]


def admin_summary() -> dict[str, Any]:
    with get_conn() as conn:
        users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
        queries = conn.execute("SELECT COUNT(*) AS c FROM query_history").fetchone()
        feedback = conn.execute("SELECT COUNT(*) AS c FROM feedback").fetchone()
        pending_feedback = conn.execute(
            "SELECT COUNT(*) AS c FROM feedback WHERE status IN ('pending', 'in_progress')"
        ).fetchone()
        overdue_feedback = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM feedback
            WHERE status IN ('pending', 'in_progress')
              AND (julianday('now') - julianday(created_at)) * 24 > 48
            """
        ).fetchone()
        active = conn.execute(
            """
            SELECT COUNT(DISTINCT user_id) AS c
            FROM query_history
            WHERE created_at >= datetime('now', '-7 days')
            """
        ).fetchone()
    return {
        "total_users": int((users or {"c": 0})["c"]),
        "total_queries": int((queries or {"c": 0})["c"]),
        "total_feedback": int((feedback or {"c": 0})["c"]),
        "pending_feedback": int((pending_feedback or {"c": 0})["c"]),
        "overdue_unprocessed": int((overdue_feedback or {"c": 0})["c"]),
        "active_users_7d": int((active or {"c": 0})["c"]),
    }


def insert_feedback(
    user_id: int,
    *,
    issue_type: str,
    content: str,
    reproducible: bool,
    severity: str = "medium",
    from_station: str | None = None,
    to_station: str | None = None,
    strategy: str | None = None,
    contact: str | None = None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO feedback
              (user_id, from_station, to_station, strategy, issue_type, severity, content, reproducible, contact)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                (from_station or "").strip() or None,
                (to_station or "").strip() or None,
                (strategy or "").strip() or None,
                issue_type.strip(),
                severity.strip(),
                content.strip(),
                1 if reproducible else 0,
                (contact or "").strip() or None,
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def list_feedback_by_user(user_id: int, limit: int = 30) -> list[dict[str, Any]]:
    limit = max(1, min(100, int(limit)))
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT
              id, from_station, to_station, strategy, issue_type, content, reproducible,
              severity,
              contact, status, resolution_note, created_at, updated_at
            FROM feedback
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def admin_list_feedback(
    limit: int = 200,
    status: str | None = None,
    issue_type: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    *,
    sla_hours: int = 48,
) -> list[dict[str, Any]]:
    limit = max(1, min(500, int(limit)))
    with get_conn() as conn:
        where: list[str] = []
        params: list[Any] = []
        if status and status != "all":
            where.append("f.status = ?")
            params.append(status)
        if issue_type and issue_type != "all":
            where.append("f.issue_type = ?")
            params.append(issue_type)
        if from_date:
            where.append("date(f.created_at) >= date(?)")
            params.append(from_date)
        if to_date:
            where.append("date(f.created_at) <= date(?)")
            params.append(to_date)
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        sql = f"""
            SELECT
              f.id, u.username, f.from_station, f.to_station, f.strategy, f.issue_type,
              f.severity, f.content, f.reproducible, f.contact, f.status, f.resolution_note,
              f.created_at, f.updated_at,
              CASE
                WHEN f.status IN ('pending', 'in_progress')
                 AND (julianday('now') - julianday(f.created_at)) * 24 > ?
                THEN 1 ELSE 0
              END AS is_overdue,
              CAST((julianday('now') - julianday(f.created_at)) * 24 AS INTEGER) AS pending_hours
            FROM feedback f
            JOIN users u ON u.id = f.user_id
            {where_sql}
            ORDER BY
              CASE
                WHEN f.status IN ('pending', 'in_progress')
                 AND (julianday('now') - julianday(f.created_at)) * 24 > ? THEN 0
                ELSE 1
              END,
              CASE f.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
              CASE f.status WHEN 'pending' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END,
              f.created_at DESC, f.id DESC
            LIMIT ?
        """
        rows = conn.execute(sql, [sla_hours, *params, sla_hours, limit]).fetchall()
        return [dict(r) for r in rows]


def admin_update_feedback_status(
    feedback_id: int, status: str, resolution_note: str | None = None
) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE feedback
            SET status = ?, resolution_note = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (status, (resolution_note or "").strip() or None, feedback_id),
        )
        conn.commit()
        return (cur.rowcount or 0) > 0


def admin_feedback_stats() -> dict[str, Any]:
    with get_conn() as conn:
        by_status_rows = conn.execute(
            """
            SELECT status, COUNT(*) AS c
            FROM feedback
            GROUP BY status
            """
        ).fetchall()
        by_issue_rows = conn.execute(
            """
            SELECT issue_type, COUNT(*) AS c
            FROM feedback
            GROUP BY issue_type
            ORDER BY c DESC
            """
        ).fetchall()
        by_severity_rows = conn.execute(
            """
            SELECT severity, COUNT(*) AS c
            FROM feedback
            GROUP BY severity
            """
        ).fetchall()
        overdue_rows = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM feedback
            WHERE status IN ('pending', 'in_progress')
              AND (julianday('now') - julianday(created_at)) * 24 > 48
            """
        ).fetchone()
    by_status = {str(r["status"]): int(r["c"]) for r in by_status_rows}
    by_issue_type = {str(r["issue_type"]): int(r["c"]) for r in by_issue_rows}
    by_severity = {str(r["severity"]): int(r["c"]) for r in by_severity_rows}
    return {
        "by_status": by_status,
        "by_issue_type": by_issue_type,
        "by_severity": by_severity,
        "overdue_unprocessed": int((overdue_rows or {"c": 0})["c"]),
    }


def admin_feedback_daily(days: int = 7) -> list[dict[str, Any]]:
    days = max(1, min(30, int(days)))
    with get_conn() as conn:
        rows = conn.execute(
            """
            WITH RECURSIVE seq(i) AS (
              SELECT 0
              UNION ALL
              SELECT i + 1 FROM seq WHERE i + 1 < ?
            )
            SELECT
              date(datetime('now', '-' || (?-1-i) || ' days')) AS d,
              COALESCE(
                (
                  SELECT COUNT(*)
                  FROM feedback f
                  WHERE date(f.created_at) = date(datetime('now', '-' || (?-1-i) || ' days'))
                ),
                0
              ) AS c
            FROM seq
            ORDER BY d ASC
            """,
            (days, days, days),
        ).fetchall()
    return [{"date": str(r["d"]), "count": int(r["c"])} for r in rows]
