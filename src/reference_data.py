"""可维护的乘客规则、禁带物品、站点无障碍数据（JSON）加载与查询。"""

from __future__ import annotations

import json
import unicodedata
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


_prohibited_items_cache: tuple[float, dict[str, Any]] | None = None


def load_prohibited_items() -> dict[str, Any]:
    """
    禁带目录可能被频繁编辑；按文件 mtime 失效缓存，改 JSON 后无需重启后端即可生效。
    """
    global _prohibited_items_cache
    path = REF_DIR / "prohibited_items.json"
    if not path.is_file():
        _prohibited_items_cache = None
        return {}
    mtime = path.stat().st_mtime
    if _prohibited_items_cache is not None and _prohibited_items_cache[0] == mtime:
        return _prohibited_items_cache[1]
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    _prohibited_items_cache = (mtime, data)
    return data


# 旧版 JSON 无 query_match_expansions 时的兜底（与 data/reference/prohibited_items.json 保持同步更好）
_FALLBACK_QUERY_EXPANSIONS: list[dict[str, Any]] = [
    {
        "if_any": ["喷雾", "喷罐", "气压罐", "压力罐", "发胶", "摩丝"],
        "if_all": [],
        "add_terms": ["喷雾", "压缩气体", "易燃液体", "压力罐"],
    },
    {
        "if_any": ["酒精", "乙醇", "消毒液", "消毒喷雾", "免洗"],
        "if_all": [],
        "add_terms": ["酒精", "易燃液体", "易燃", "喷雾", "消毒"],
    },
    {
        "if_any": ["打火机", "火柴", "燃料罐"],
        "if_all": [],
        "add_terms": ["打火机", "易燃气体", "易燃"],
    },
    {
        "if_any": [
            "宠物",
            "猫",
            "狗",
            "犬",
            "鸟",
            "活禽",
            "仓鼠",
            "兔子",
            "小猫",
            "小狗",
            "猫咪",
            "狗狗",
        ],
        "if_all": [],
        "add_terms": ["活禽", "活动物", "动物", "宠物"],
    },
    {
        "if_any": ["刀", "匕"],
        "if_all": [],
        "add_terms": ["刀", "匕首", "管制", "锐器", "钝器"],
    },
    {
        "if_any": ["烟花", "爆竹", "礼花", "鞭炮"],
        "if_all": [],
        "add_terms": ["烟花", "爆竹", "烟火", "爆炸"],
    },
    {
        "if_any": ["硫酸", "盐酸", "电池酸", "水银", "汞", "农药"],
        "if_all": [],
        "add_terms": ["腐蚀", "有毒", "剧毒", "酸", "汞"],
    },
]


def _expansion_table(raw: dict[str, Any]) -> list[dict[str, Any]]:
    rows = raw.get("query_match_expansions")
    if isinstance(rows, list) and rows:
        return [r for r in rows if isinstance(r, dict)]
    return list(_FALLBACK_QUERY_EXPANSIONS)


def _prohibited_match_terms(query: str, raw: dict[str, Any]) -> set[str]:
    """
    用户原句 + 配置表触发的 add_terms，用于与目录正文做子串匹配。
    规则维护：编辑 prohibited_items.json 的 query_match_expansions。
    """
    q = (query or "").strip()
    terms: set[str] = set()
    if q:
        terms.add(q)
    if not q:
        return terms
    for row in _expansion_table(raw):
        if_any = row.get("if_any") or []
        if_all = row.get("if_all") or []
        add_terms = row.get("add_terms") or []
        if not isinstance(if_any, list):
            if_any = []
        if not isinstance(if_all, list):
            if_all = []
        if not isinstance(add_terms, list):
            continue
        if not if_any and not if_all:
            continue
        cond_any = (not if_any) or any(
            isinstance(x, str) and x and x in q for x in if_any
        )
        cond_all = (not if_all) or all(
            isinstance(x, str) and x and x in q for x in if_all
        )
        if cond_any and cond_all:
            for t in add_terms:
                if isinstance(t, str) and t.strip():
                    terms.add(t.strip())
    return terms


def _term_matches_line(term: str, line: str, original_query: str) -> bool:
    if not term or not line:
        return False
    if len(term) >= 2:
        return term in line or term.casefold() in line.casefold()
    if len(original_query.strip()) <= 2:
        return term in line
    return False


def _normalize_prohibited_query(query: str) -> str:
    """统一全角半角与兼容组合字符，减少「看起来一样却匹配失败」的情况。"""
    q = (query or "").strip()
    if not q:
        return ""
    return unicodedata.normalize("NFKC", q)


def _boost_live_animal_terms(q: str, terms: set[str]) -> None:
    """
    活禽/宠物：代码层硬兜底，不依赖 JSON 是否被旧进程缓存或未保存。
    注意：不用单字「鼠」以免误伤「鼠标」等；仓鼠等整词已在短语表中。
    """
    if not q:
        return
    phrases = (
        "宠物",
        "萌宠",
        "小宠",
        "活禽",
        "仓鼠",
        "兔子",
        "龙猫",
        "荷兰猪",
        "刺猬",
        "鹦鹉",
        "鸟笼",
        "鸡鸭",
        "爬行",
        "蜥蜴",
        "蛇",
        "金鱼",
        "乌龟",
        "带猫",
        "带狗",
        "能不能带动物",
        "小动物",
    )
    if any(p in q for p in phrases):
        terms.update(["活禽", "活动物", "动物"])
    if "宠" in q or "猫" in q or "狗" in q or "犬" in q:
        terms.update(["活禽", "活动物", "动物"])
    if "鸟" in q and "鸵鸟" not in q:
        terms.update(["活禽", "活动物", "动物"])
    if "喵" in q or "汪" in q:
        terms.update(["活禽", "活动物", "动物"])


def _is_live_animal_question(q: str) -> bool:
    if not q:
        return False
    probe: set[str] = set()
    _boost_live_animal_terms(q, probe)
    return bool(probe)


def _fallback_live_animal_match(
    q: str, categories: list[Any], footer: str
) -> dict[str, Any] | None:
    """仍无命中时，直接引用「活禽、活动物」条文（保证演示可用）。"""
    for cat in categories:
        if not isinstance(cat, dict):
            continue
        if str(cat.get("id") or "") != "odor_pollute":
            continue
        items = cat.get("items") or []
        pick = ""
        for it in items:
            if isinstance(it, str) and "活禽" in it:
                pick = it.strip()
                break
        if not pick and items and isinstance(items[0], str):
            pick = items[0].strip()
        if not pick:
            return None
        return {
            "query": q,
            "verdict": "likely_prohibited",
            "summary": "在演示禁带目录中检索到相关说明：下列类别与您输入有关，通常禁止或严格限制携带。最终以车站安检与法规为准。",
            "matches": [
                {
                    "category_id": cat.get("id"),
                    "label": cat.get("label"),
                    "short_label": cat.get("short_label"),
                    "icon": cat.get("icon"),
                    "color": cat.get("color"),
                    "matched_snippets": [pick],
                    "note": (cat.get("note") or "").strip(),
                }
            ],
            "footer": footer,
        }
    return None


def check_prohibited_carry(query: str) -> dict[str, Any]:
    """
    按演示用禁带目录做关键词命中（子串匹配），供乘客自助查询「某物是否可能禁带」。
    未命中不代表一定可带，最终以法规与安检现场为准。
    """
    q = _normalize_prohibited_query(query)
    raw = load_prohibited_items()
    footer = str(raw.get("footer") or "").strip()
    if not q:
        return {
            "query": "",
            "verdict": "empty",
            "summary": "请输入要查询的物品名称，例如：打火机、酒精、宠物、水果刀。",
            "matches": [],
            "footer": footer,
        }
    categories = raw.get("categories")
    if not isinstance(categories, list):
        categories = []
    match_terms = _prohibited_match_terms(q, raw)
    _boost_live_animal_terms(q, match_terms)
    matches: list[dict[str, Any]] = []

    for cat in categories:
        if not isinstance(cat, dict):
            continue
        snippets: list[str] = []
        seen: set[str] = set()

        def consider(text: object) -> None:
            if not isinstance(text, str):
                return
            t = text.strip()
            if not t:
                return
            hit = any(_term_matches_line(term, t, q) for term in match_terms)
            if hit and t not in seen:
                seen.add(t)
                snippets.append(t)

        consider(cat.get("label"))
        consider(cat.get("short_label"))
        for ex in cat.get("examples") or []:
            consider(ex)
        for it in cat.get("items") or []:
            consider(it)
        consider(cat.get("note"))

        if snippets:
            matches.append(
                {
                    "category_id": cat.get("id"),
                    "label": cat.get("label"),
                    "short_label": cat.get("short_label"),
                    "icon": cat.get("icon"),
                    "color": cat.get("color"),
                    "matched_snippets": snippets,
                    "note": (cat.get("note") or "").strip(),
                }
            )

    matches.sort(key=lambda m: -len(m.get("matched_snippets") or []))
    if matches:
        return {
            "query": q,
            "verdict": "likely_prohibited",
            "summary": "在演示禁带目录中检索到相关说明：下列类别与您输入有关，通常禁止或严格限制携带。最终以车站安检与法规为准。",
            "matches": matches,
            "footer": footer,
        }
    if _is_live_animal_question(q):
        fb = _fallback_live_animal_match(q, categories, footer)
        if fb:
            return fb
    return {
        "query": q,
        "verdict": "no_direct_hit",
        "summary": "演示数据中未找到与您输入直接对应的禁带条目。常见日用品在符合行李重量、尺寸要求时一般可携带；若属于易燃品、压力罐装喷雾、刀具、活禽宠物等敏感类，建议不要携带或提前向运营方核实。",
        "matches": [],
        "footer": footer,
    }


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
