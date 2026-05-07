"""
将 data/luxian 下的线路与元数据中的换乘信息同步到 SQLite 镜像表（sys_*），
供 DataGrip 等工具直观浏览；不参与路径规划核心逻辑（仍以 JSON5 为准）。
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from . import auth_db
from .data_loader import iter_line_documents, load_metadata

log = logging.getLogger(__name__)

MIRROR_VERSION = "1"


def _clear_mirror_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DELETE FROM sys_transfers;
        DELETE FROM sys_stations;
        DELETE FROM sys_lines;
        """
    )


def _insert_lines_and_stations(conn: sqlite3.Connection) -> None:
    for source_file, doc in iter_line_documents():
        name = (doc.get("name") or "").strip() or source_file
        color = (doc.get("color") or "") or None
        stations = doc.get("stations") or []
        n = len(stations)
        conn.execute(
            "INSERT INTO sys_lines (line_name, color, source_file, station_count) VALUES (?, ?, ?, ?)",
            (name, color, source_file, n),
        )
        for j, st in enumerate(stations):
            stname = (st.get("name") or "").strip()
            al = st.get("aliases") or []
            aliases_str = None
            if isinstance(al, list) and al:
                aliases_str = "、".join(str(x) for x in al)
            dist_next: float | None = None
            if j + 1 < len(stations):
                nxt = stations[j + 1]
                if isinstance(nxt, dict) and nxt.get("dist") is not None:
                    try:
                        dist_next = float(nxt["dist"])
                    except (TypeError, ValueError):
                        dist_next = None
            conn.execute(
                """
                INSERT INTO sys_stations (line_name, seq, station_name, dist_to_next_m, aliases)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, j, stname, dist_next, aliases_str),
            )


def _insert_transfers(conn: sqlite3.Connection) -> None:
    meta: dict[str, Any] = load_metadata()
    transfers = meta.get("transfers")
    if not isinstance(transfers, dict):
        return
    for hub, rules in transfers.items():
        if not isinstance(rules, list):
            continue
        hub_s = str(hub).strip()
        for r in rules:
            if not isinstance(r, dict):
                continue
            fr = str(r.get("from", "") or "").strip()
            to = str(r.get("to", "") or "").strip()
            mins: float | None
            try:
                raw = r.get("minutes")
                mins = float(raw) if raw is not None else None
            except (TypeError, ValueError):
                mins = None
            extra: dict[str, Any] = {}
            for k, v in r.items():
                if k in ("from", "to", "minutes"):
                    continue
                extra[k] = v
            extra_s = json.dumps(extra, ensure_ascii=False) if extra else None
            conn.execute(
                """
                INSERT INTO sys_transfers (hub_station, from_line, to_line, walk_minutes, extra_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (hub_s, fr, to, mins, extra_s),
            )


def sync_mirrored_system_tables() -> None:
    """
    清空并重新填充 sys_lines / sys_stations / sys_transfers，并写入 sys_sync_meta。
    应在 ensure_db() 之后调用。
    """
    auth_db.ensure_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with auth_db.get_conn() as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        _clear_mirror_tables(conn)
        _insert_lines_and_stations(conn)
        _insert_transfers(conn)
        n_lines = conn.execute("SELECT COUNT(*) FROM sys_lines").fetchone()[0]
        n_st = conn.execute("SELECT COUNT(*) FROM sys_stations").fetchone()[0]
        n_tr = conn.execute("SELECT COUNT(*) FROM sys_transfers").fetchone()[0]
        conn.execute("DELETE FROM sys_sync_meta")
        conn.executemany(
            "INSERT INTO sys_sync_meta (k, v) VALUES (?, ?)",
            [
                ("mirror_version", MIRROR_VERSION),
                ("last_sync_utc", now),
                ("line_count", str(n_lines)),
                ("station_row_count", str(n_st)),
                ("transfer_row_count", str(n_tr)),
            ],
        )
        conn.commit()
    log.info(
        "系统数据已同步到 SQLite 镜像表：lines=%s stations=%s transfers=%s",
        n_lines,
        n_st,
        n_tr,
    )


def mirror_summary() -> dict[str, str]:
    """供调试或管理接口只读获取镜像元信息（可选）。"""
    auth_db.ensure_db()
    with auth_db.get_conn() as conn:
        cur = conn.execute("SELECT k, v FROM sys_sync_meta ORDER BY k")
        return {str(r[0]): str(r[1]) for r in cur.fetchall()}
