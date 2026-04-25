"""结果导出：UTF-8 文本与 JSON（便于验收与答辩展示）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_text_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def plan_to_serializable(
    plan_label: str,
    nodes: list[tuple[str, str]],
    total_time_min: float,
    transfer_count: int,
    fare_yuan: int,
) -> dict[str, Any]:
    return {
        "objective": plan_label,
        "total_time_minutes_rounded": round(total_time_min, 2),
        "transfer_count": transfer_count,
        "estimated_fare_yuan": fare_yuan,
        "steps": [{"line": ln, "station": st} for ln, st in nodes],
    }
