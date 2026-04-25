"""
加载 data/luxian 下的线路 JSON5、换乘元数据与票价规则。
答辩说明：数据层与算法层分离，便于替换官方 API 或更新线路图。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import difflib

import json5

from .config import DATA_LUXIAN_DIR


def _read_json5(path: Path) -> Any:
    raw = path.read_bytes()
    text: str | None = None
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="replace")
    try:
        return json5.loads(text)
    except Exception as e:
        raise ValueError(f"无法解析 JSON5：{path.name} — {e}") from e


def iter_line_documents() -> list[tuple[str, dict[str, Any]]]:
    """按文件名排序迭代线路定义（文件名, 文档对象），供清洗层使用。"""
    skip = {
        "metadata.json5",
        "fare_rules.json5",
        "carriage_types.json5",
    }
    out: list[tuple[str, dict[str, Any]]] = []
    for p in sorted(DATA_LUXIAN_DIR.glob("*.json5")):
        if p.name in skip:
            continue
        out.append((p.name, _read_json5(p)))
    return out


def load_metadata() -> dict[str, Any]:
    return _read_json5(DATA_LUXIAN_DIR / "metadata.json5")


def load_fare_rules() -> dict[str, Any]:
    return _read_json5(DATA_LUXIAN_DIR / "fare_rules.json5")


def load_line_files() -> list[dict[str, Any]]:
    """读取所有线路定义文件（排除元数据与票价等）。未做结构校验，生产路径请用 data_cleaning.load_clean_network_bundle。"""
    return [doc for _fname, doc in iter_line_documents()]


def station_segments_for_line(line_doc: dict[str, Any]) -> tuple[str, list[tuple[str, str, int]]]:
    """
    从单条线路文档解析相邻站间距离（米）。
    返回：(线路名, [(前站, 后站, 距离米), ...])，双向乘车均适用同一数值。
    """
    line_name = line_doc["name"]
    stations = line_doc["stations"]
    edges: list[tuple[str, str, int]] = []
    prev_name: str | None = None
    for st in stations:
        name = st["name"]
        if prev_name is not None:
            dist = int(st["dist"])
            edges.append((prev_name, name, dist))
        prev_name = name
    return line_name, edges


def build_station_alias_index(line_docs: list[dict[str, Any]]) -> dict[str, list[str]]:
    """站名别名 -> 规范站名列表（用于模糊查询）。"""
    alias_to_canonical: dict[str, list[str]] = {}
    for doc in line_docs:
        for st in doc["stations"]:
            canonical = st["name"]
            for key in [canonical, *st.get("aliases", [])]:
                key_norm = key.strip()
                alias_to_canonical.setdefault(key_norm.lower(), []).append(canonical)
    # 去重保持顺序
    out: dict[str, list[str]] = {}
    for k, v in alias_to_canonical.items():
        seen: set[str] = set()
        uniq: list[str] = []
        for c in v:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        out[k] = uniq
    return out


def resolve_station_query(
    query: str,
    alias_index: dict[str, list[str]],
) -> list[str]:
    """
    将用户输入解析为数据中的规范站名。
    若存在多个候选（同名不同站），返回全部供上层提示。
    """
    q = query.strip()
    if not q:
        return []

    def norm(s: str) -> str:
        x = s.strip().lower()
        for suffix in ("地铁站", "地铁", "站"):
            if x.endswith(suffix):
                x = x[: -len(suffix)]
        return x

    lowered = norm(q)
    if lowered in alias_index:
        return list(alias_index[lowered])

    # 简单包含匹配：便于答辩演示输入简称
    hits: list[str] = []
    all_names: list[str] = []
    for canon_list in alias_index.values():
        for c in canon_list:
            all_names.append(c)
            if q in c or c in q:
                hits.append(c)
    # 去重
    seen: set[str] = set()
    uniq: list[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            uniq.append(h)
    if uniq:
        return uniq

    # 错别字/近似输入兜底匹配（编辑距离近似）
    canon_uniq = list(dict.fromkeys(all_names))
    close = difflib.get_close_matches(q, canon_uniq, n=5, cutoff=0.72)
    if close:
        return close
    # 使用规范化字符串再试一次（如“国贸地铁”->“国贸”）
    close_norm = difflib.get_close_matches(lowered, [norm(x) for x in canon_uniq], n=5, cutoff=0.8)
    if close_norm:
        out: list[str] = []
        for c in canon_uniq:
            if norm(c) in close_norm and c not in out:
                out.append(c)
        return out
    return []
