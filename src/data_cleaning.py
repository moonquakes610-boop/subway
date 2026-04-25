"""
数据读取后的校验与清洗：保证路网构建前数据一致、可答辩说明「数据流水线」。
"""

from __future__ import annotations

import logging
from typing import Any

from .errors import DataValidationError

log = logging.getLogger(__name__)


def _strip_str(v: Any, ctx: str) -> str:
    if not isinstance(v, str):
        raise DataValidationError(f"{ctx}：期望字符串，实际为 {type(v).__name__}")
    s = v.strip()
    if not s:
        raise DataValidationError(f"{ctx}：字符串为空")
    return s


def validate_line_document(doc: dict[str, Any], source_name: str) -> dict[str, Any]:
    """
    校验单条线路 JSON 对象，返回清洗后的浅拷贝结构（站名字符串 strip）。
    不满足条件时抛出 DataValidationError。
    """
    if not isinstance(doc, dict):
        raise DataValidationError(f"{source_name}：根对象必须是字典")

    line_name = _strip_str(doc.get("name"), f"{source_name}.name")
    stations_raw = doc.get("stations")
    if not isinstance(stations_raw, list) or not stations_raw:
        raise DataValidationError(f"{source_name}：stations 必须为非空列表")

    cleaned_stations: list[dict[str, Any]] = []
    for i, st in enumerate(stations_raw):
        if not isinstance(st, dict):
            raise DataValidationError(f"{source_name}：第 {i} 个站点不是对象")
        name = _strip_str(st.get("name"), f"{source_name}.stations[{i}].name")
        entry: dict[str, Any] = {"name": name}
        if "aliases" in st and st["aliases"] is not None:
            als = st["aliases"]
            if not isinstance(als, list):
                raise DataValidationError(f"{source_name}.stations[{i}].aliases 必须为列表")
            entry["aliases"] = [_strip_str(a, f"alias[{j}]") for j, a in enumerate(als)]
        dist = st.get("dist")
        if i > 0:
            if dist is None:
                raise DataValidationError(
                    f"{source_name}：站点「{name}」缺少 dist（首站可无 dist）"
                )
            try:
                d = int(dist)
            except (TypeError, ValueError) as e:
                raise DataValidationError(
                    f"{source_name}：站点「{name}」dist 非法：{dist!r}"
                ) from e
            if d <= 0:
                raise DataValidationError(f"{source_name}：站点「{name}」dist 必须为正整数")
            entry["dist"] = d
        cleaned_stations.append(entry)

    out = {**doc, "name": line_name, "stations": cleaned_stations}
    return out


def validate_metadata(doc: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(doc, dict):
        raise DataValidationError("metadata.json5：根对象必须是字典")
    transfers = doc.get("transfers")
    if transfers is not None and not isinstance(transfers, dict):
        raise DataValidationError("metadata.json5：transfers 必须为对象")
    return doc


def validate_fare_rules(doc: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(doc, dict):
        raise DataValidationError("fare_rules.json5：根对象必须是字典")
    if "rule_groups" not in doc:
        raise DataValidationError("fare_rules.json5：缺少 rule_groups")
    return doc


def load_clean_network_bundle() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """
    读取并清洗线路、元数据、票价规则。
    返回：(清洗后的线路文档列表, metadata, fare_rules)
    """
    from . import data_loader

    try:
        metadata = validate_metadata(data_loader.load_metadata())
        fare = validate_fare_rules(data_loader.load_fare_rules())
    except (OSError, ValueError, DataValidationError):
        raise
    except Exception as e:
        raise DataValidationError(f"读取元数据或票价规则失败：{e}") from e

    lines: list[dict[str, Any]] = []
    try:
        for fname, doc in data_loader.iter_line_documents():
            lines.append(validate_line_document(doc, fname))
            log.debug("线路文件已校验：%s", fname)
    except (OSError, ValueError, DataValidationError):
        raise
    except Exception as e:
        log.error("读取线路数据失败：%s", e)
        raise DataValidationError(f"读取线路数据失败：{e}") from e

    if not lines:
        log.error("data/luxian 下无可用线路文件（PROJECT_ROOT=%s）", data_loader.DATA_LUXIAN_DIR)
        raise DataValidationError(
            "未加载到任何线路文件，请检查 data/luxian 目录是否存在 JSON5 线路数据。"
        )
    return lines, metadata, fare
