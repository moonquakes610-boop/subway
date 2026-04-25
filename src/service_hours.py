from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .pathfinder import PlanResult

_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")


def _time_to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _minutes_now_local() -> int:
    now = datetime.now()
    return now.hour * 60 + now.minute


def _fmt_minutes(m: int) -> str:
    m = max(0, min(24 * 60 - 1, int(m)))
    return f"{m // 60:02d}:{m % 60:02d}"


def _extract_times_from_obj(obj: Any, out: list[int]) -> None:
    if isinstance(obj, str):
        for m in _TIME_RE.finditer(obj):
            out.append(int(m.group(1)) * 60 + int(m.group(2)))
        return
    if isinstance(obj, dict):
        for v in obj.values():
            _extract_times_from_obj(v, out)
        return
    if isinstance(obj, list):
        for x in obj:
            _extract_times_from_obj(x, out)


def build_line_service_windows(line_docs: list[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    """
    解析每条线的服务窗口（分钟）。
    若无可解析时刻，回退到保守默认 05:00-23:00。
    """
    windows: dict[str, tuple[int, int]] = {}
    for doc in line_docs:
        line = str(doc.get("name") or "").strip()
        if not line:
            continue
        vals: list[int] = []
        _extract_times_from_obj(doc, vals)
        if vals:
            windows[line] = (min(vals), max(vals))
        else:
            windows[line] = (5 * 60, 23 * 60)
    return windows


def validate_plan_service_time(
    plan: PlanResult,
    windows: dict[str, tuple[int, int]],
    start_minutes: int | None = None,
) -> tuple[bool, str]:
    """
    依据线路服务窗口判断当前时刻是否可达（简化模型）：
    - 出发时刻需晚于起始线路首班
    - 进入任一线路时刻不得晚于该线路末班
    """
    t = _minutes_now_local() if start_minutes is None else int(start_minutes)
    t = max(0, min(24 * 60 - 1, t))
    if not plan.nodes:
        return False, "路径为空。"
    for idx, (line, _st) in enumerate(plan.nodes):
        win = windows.get(line)
        if not win:
            continue
        first_m, last_m = win
        if idx == 0 and t < first_m:
            return (
                False,
                f"当前时刻早于 {line} 首班车约 {_fmt_minutes(first_m)}。",
            )
        if t > last_m:
            return (
                False,
                f"当前时刻已晚于 {line} 末班服务时间（约 {_fmt_minutes(last_m)} 后线路停运/不再接纳进站，模型简化）。",
            )
        if len(plan.nodes) > 1:
            t += max(1, int(round(plan.total_time_min / (len(plan.nodes) - 1))))
    return True, ""


def _line_window_row(
    line: str,
    windows: dict[str, tuple[int, int]],
    t_query: int,
) -> dict[str, Any]:
    win = windows.get(line) or (5 * 60, 23 * 60)
    first_m, last_m = int(min(win[0], win[1])), int(max(win[0], win[1]))
    in_at_query = first_m <= t_query <= last_m
    return {
        "line": line,
        "first_hhmm": _fmt_minutes(first_m),
        "last_hhmm": _fmt_minutes(last_m),
        "first_minutes": first_m,
        "last_minutes": last_m,
        "in_service_at_query": in_at_query,
    }


def build_plan_service_briefing(
    plan: PlanResult,
    windows: dict[str, tuple[int, int]],
    start_minutes: int | None = None,
) -> dict[str, Any]:
    """
    为「仍有路线、但某时刻可能不可行」的答辩说辞准备结构化信息：
    - 保留路径展示；用 ok/文案说明当前「查询时刻」下是否可乘车。
    - lines：本次路径按首次出现线路列出首/末时间（从数据或默认 05:00–23:00 推断，演示用）。
    """
    t0 = _minutes_now_local() if start_minutes is None else int(start_minutes)
    t0 = max(0, min(24 * 60 - 1, t0))
    ok, err_msg = validate_plan_service_time(plan, windows, t0)
    # 路径中按序首次出现的线路
    order: list[str] = []
    seen: set[str] = set()
    for line, _ in plan.nodes:
        if line and line not in seen:
            seen.add(line)
            order.append(line)
    line_rows: list[dict[str, Any]] = [
        _line_window_row(ln, windows, t0) for ln in order
    ]
    qh = _fmt_minutes(t0)
    if ok:
        head = f"在简化首末班模型下，以查询时刻 {qh} 出发，本路径在涉及线路的对外服务时间窗内，可按图乘车（模型演示，以现场与时刻表为准）。"
    else:
        head = (
            f"【时段提示】规划结果仍为一条完整乘车路线，但按当前「查询时刻 {qh}」与简化首末班模型，"
            f"该方案在此时段不可按图乘车。原因：{err_msg} "
            f"下表为本次路径所涉线路的参考首、末时间（自数据内时刻文本推断，缺省 05:00–23:00，仅供参考；停运后仍有路径仅表示线网图上的可联通性，不代表可乘车。）"
        )
    return {
        "ok": ok,
        "query_hhmm": qh,
        "query_minutes": t0,
        "message": err_msg,
        "headline": head,
        "lines": line_rows,
    }
