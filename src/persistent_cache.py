"""
路网构建结果磁盘缓存：避免每次 CLI 重复解析全部 JSON5（便于满足「查询 ≤2 秒」验收）。

缓存键：data/luxian 下各 json5 的修改时间指纹；数据变更后自动重建。
"""

from __future__ import annotations

import hashlib
import logging
import pickle
from pathlib import Path
from typing import Any

from .config import DATA_LUXIAN_DIR, PROJECT_ROOT
from .data_cleaning import load_clean_network_bundle
from .network_graph import Edge, Node, build_graph

log = logging.getLogger(__name__)


def _luxian_fingerprint() -> str:
    h = hashlib.sha256()
    for p in sorted(DATA_LUXIAN_DIR.glob("*.json5")):
        h.update(p.name.encode("utf-8"))
        h.update(str(p.stat().st_mtime_ns).encode("ascii"))
    return h.hexdigest()[:20]


def _cache_path() -> Path:
    return PROJECT_ROOT / "output" / f"network_graph_{_luxian_fingerprint()}.pkl"


def load_or_build_cached_network(
    force_rebuild: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[Node, list[Edge]]]:
    path = _cache_path()
    if not force_rebuild and path.is_file():
        try:
            with path.open("rb") as f:
                payload = pickle.load(f)
            log.info("命中路网缓存：%s", path.name)
            return (
                payload["line_docs"],
                payload["metadata"],
                payload["fare_doc"],
                payload["graph"],
            )
        except (OSError, pickle.PickleError, KeyError, TypeError) as e:
            log.error("缓存读取失败，将重建：%s", e)

    log.info("构建路网并写入缓存（force_rebuild=%s）…", force_rebuild)
    line_docs, metadata, fare_doc = load_clean_network_bundle()
    graph = build_graph(line_docs, metadata)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            pickle.dump(
                {
                    "line_docs": line_docs,
                    "metadata": metadata,
                    "fare_doc": fare_doc,
                    "graph": graph,
                },
                f,
            )
        log.info("已写入缓存：%s", path.name)
    except OSError as e:
        log.error("写入缓存失败（仍可继续本次查询）：%s", e)
    return line_docs, metadata, fare_doc, graph
