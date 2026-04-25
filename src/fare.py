"""
根据 fare_rules.json5 对路径做票价估算（毕业设计演示版）。

说明：
- 大路网：按乘车路径的累计里程（米）分段计价；
- 首都机场线：按次固定票价；
- 大兴机场线、西郊线：按各自里程规则；
- 未实现：低峰优惠、合并计费细则等，可在论文「不足与展望」中说明。
"""

from __future__ import annotations

from typing import Any

from .config import SPECIAL_FARE_LINES


def _bracket_fare(distance_m: int, rules: list[dict[str, Any]]) -> int:
    """在有序规则表中匹配里程所在区间，返回票价（元）。"""
    for r in rules:
        start = int(r.get("start", 0))
        end = r.get("end")
        end_v = int(end) if end is not None else 10**12
        if start <= distance_m <= end_v:
            return int(r["fare"])
    return int(rules[-1]["fare"])


def estimate_fare_yuan(fare_doc: dict[str, Any], meters_by_line: dict[str, int]) -> tuple[int, list[str]]:
    """
    输入：各线路上实际经过的轨道里程（米）。
    返回：(总票价元, 明细说明行)。
    """
    groups = fare_doc["rule_groups"]
    notes: list[str] = []

    def find_group(name: str) -> dict[str, Any]:
        for g in groups:
            if g.get("name") == name:
                return g
        raise KeyError(name)

    main_group = find_group("大路网")
    main_rules = main_group["rules"]

    main_dist = sum(m for ln, m in meters_by_line.items() if ln not in SPECIAL_FARE_LINES)
    main_fare = _bracket_fare(main_dist, main_rules)
    notes.append(f"大路网里程约 {main_dist / 1000:.2f} km，适用「{main_group['name']}」规则：{main_fare} 元")

    total = main_fare

    airport = meters_by_line.get("首都机场线", 0)
    if airport > 0:
        ap_rules = find_group("首都机场线")["rules"]
        ap_fare = int(ap_rules[0]["fare"])
        total += ap_fare
        notes.append(f"含首都机场线乘车：+{ap_fare} 元（单次计价演示）")

    daxing = meters_by_line.get("大兴机场线", 0)
    if daxing > 0:
        dx_group = find_group("大兴机场线")
        dx_fare = _bracket_fare(daxing, dx_group["rules"])
        total += dx_fare
        notes.append(f"大兴机场线里程约 {daxing / 1000:.2f} km：+{dx_fare} 元")

    xijiao = meters_by_line.get("西郊线", 0)
    if xijiao > 0:
        xj_group = find_group("有轨电车")  # 数据文件中名称
        xj_fare = _bracket_fare(xijiao, xj_group["rules"])
        total += xj_fare
        notes.append(f"西郊线（有轨电车）里程约 {xijiao / 1000:.2f} km：+{xj_fare} 元")

    notes.append(f"估算合计：{total} 元（演示算法，非官方计费）")
    return total, notes
