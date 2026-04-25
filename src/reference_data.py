"""可维护的乘客规则、禁带物品、站点无障碍数据（JSON）加载与查询。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REF_DIR = ROOT / "data" / "reference"

FIELD_LABELS: dict[str, str] = {
    "accessibility_elevator": "无障碍电梯",
    "accessibility_toilet": "无障碍卫生间",
    "ramp": "坡道",
    "blind_path": "盲道",
    "service_center": "客服中心位置",
    "remark": "备注",
}


@lru_cache(maxsize=4)
def _read_json(name: str) -> dict[str, Any]:
    path = REF_DIR / name
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_passenger_rules() -> dict[str, Any]:
    return _read_json("passenger_rules.json")


def load_prohibited_items() -> dict[str, Any]:
    return _read_json("prohibited_items.json")


def load_station_accessibility_raw() -> dict[str, Any]:
    return _read_json("station_accessibility.json")


def load_runtime_status() -> dict[str, Any]:
    data = _read_json("runtime_status.json")
    if data:
        return data
    return {
        "version": "builtin-fallback",
        "updated_at": "",
        "overall": "unknown",
        "summary": "暂未接入实时运营数据，请以车站公告和官方 App 为准。",
        "lines": [],
    }


def accessibility_field_value(station_key: str, field: str, raw: dict[str, Any] | None = None) -> str:
    """单站单字段；无数据或空字符串时返回「暂未收录」。"""
    if raw is None:
        raw = load_station_accessibility_raw()
    stations = raw.get("stations") or {}
    st = stations.get(station_key.strip()) if station_key else None
    if not isinstance(st, dict):
        return "暂未收录"
    val = st.get(field)
    if val is None or (isinstance(val, str) and not val.strip()):
        return "暂未收录"
    s = str(val).strip()
    if s in ("暂无", "无", "—", "-", "N/A", "n/a"):
        return "暂未收录"
    return s


def batch_station_accessibility(station_names: list[str]) -> dict[str, Any]:
    """
    返回 { ok, meta, stations: { 站名: { role仅前端需要可忽略, 各字段+labels } } }
    每个站包含已定义字段的展示文本；无键则 暂未收录。
    """
    raw = load_station_accessibility_raw()
    meta = raw.get("meta") or {}
    out_stations: dict[str, Any] = {}
    for name in station_names:
        key = (name or "").strip()
        if not key:
            continue
        st_info: dict[str, Any] = {}
        for fkey, flabel in FIELD_LABELS.items():
            st_info[fkey] = {
                "label": flabel,
                "value": accessibility_field_value(key, fkey, raw),
            }
        out_stations[key] = st_info
    return {
        "ok": True,
        "meta": meta,
        "field_order": list(FIELD_LABELS.keys()),
        "stations": out_stations,
    }
