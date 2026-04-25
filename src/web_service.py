"""
供 HTTP 服务调用的规划入口：与 CLI 复用相同算法与数据。
"""

from __future__ import annotations

import time
from typing import Any, Literal

from .data_loader import build_station_alias_index, resolve_station_query
from .errors import (
    InputError,
    RouteNotFoundError,
    StationNotFoundError,
    SubwayGuideError,
)
from .export_results import plan_to_serializable
from .fare import estimate_fare_yuan
from .guide_generator import generate_personalized_plan_guide
from .network_graph import nodes_at_station
from .pathfinder import dijkstra_min_time, dijkstra_min_transfer_then_time, path_track_meters_by_line
from .persistent_cache import load_or_build_cached_network
from .service_hours import (
    build_line_service_windows,
    build_plan_service_briefing,
    validate_plan_service_time,
)

StrategyKey = Literal["min_time", "min_transfer", "compare"]


def _resolve_unique_station(
    raw: str,
    alias_index: dict[str, list[str]],
    role: str,
) -> str:
    q = raw.strip() if raw else ""
    if not q:
        raise InputError(f"{role}不能为空，请输入站点名称。")
    names = resolve_station_query(q, alias_index)
    if not names:
        raise StationNotFoundError(f"未找到与「{q}」匹配的站点，请检查拼写或换用数据中的规范站名。")
    if len(names) > 1:
        detail = "\n".join(f"  - {n}" for n in names)
        raise StationNotFoundError(
            f"「{q}」对应多个候选站点（{role}），请更精确输入：\n{detail}"
        )
    return names[0]


def query_route(
    frm: str,
    to: str,
    strategy: StrategyKey,
    *,
    guide_mode: str = "commute",
    force_rebuild_cache: bool = False,
    query_time_minutes: int | None = None,
) -> dict[str, Any]:
    """
    返回供 JSON 序列化的成功结果字典；业务异常应转换为 HTTP 层错误响应。
    """
    t0 = time.perf_counter()
    line_docs, metadata, fare_doc, graph = load_or_build_cached_network(
        force_rebuild=force_rebuild_cache,
    )
    t_after_load = time.perf_counter()

    alias_index = build_station_alias_index(line_docs)
    start_station = _resolve_unique_station(frm, alias_index, "起点")
    end_station = _resolve_unique_station(to, alias_index, "终点")

    if start_station == end_station:
        raise InputError("起点与终点相同，无需乘车；请重新输入。")

    sources = nodes_at_station(graph, start_station)
    goals = set(nodes_at_station(graph, end_station))
    if not sources:
        raise StationNotFoundError(
            f"起点「{start_station}」未出现在路网顶点中（数据可能未收录该站或清洗失败）。"
        )
    if not goals:
        raise StationNotFoundError(
            f"终点「{end_station}」未出现在路网顶点中（数据可能未收录该站或清洗失败）。"
        )

    plan_time = dijkstra_min_time(graph, sources, goals)
    plan_xfer = dijkstra_min_transfer_then_time(graph, sources, goals)

    if plan_time is None or plan_xfer is None:
        raise RouteNotFoundError(
            "起点与终点在当前数据与换乘模型下不连通，或缺少换乘定义；请尝试其他站点。"
        )

    if strategy == "min_time":
        chosen = plan_time
        recommendation_reason = "你选择了“最短时间”，系统按预计总耗时最小返回结果。"
    elif strategy == "min_transfer":
        chosen = plan_xfer
        recommendation_reason = "你选择了“最少换乘”，系统按换乘次数最少返回结果。"
    else:
        time_delta = plan_xfer.total_time_min - plan_time.total_time_min
        if time_delta <= 8:
            chosen = plan_xfer
            recommendation_reason = (
                "对比策略：两方案耗时接近，优先推荐换乘更少的路线，乘车压力更低。"
            )
        else:
            chosen = plan_time
            recommendation_reason = (
                "对比策略：最短时间方案节省时间明显，优先推荐更快到达路线。"
            )
    windows = build_line_service_windows(line_docs)
    ok_time, msg_time = validate_plan_service_time(
        plan_time, windows, query_time_minutes
    )
    ok_xfer, msg_xfer = validate_plan_service_time(
        plan_xfer, windows, query_time_minutes
    )
    feasible_keys: list[str] = []
    if ok_time:
        feasible_keys.append("min_time")
    if ok_xfer:
        feasible_keys.append("min_transfer")

    if strategy == "min_time":
        ok_service = ok_time
        service_msg = msg_time
    elif strategy == "min_transfer":
        ok_service = ok_xfer
        service_msg = msg_xfer
    else:
        ok_service = ok_time if chosen is plan_time else ok_xfer
        service_msg = msg_time if chosen is plan_time else msg_xfer
    # 不自动改推荐方案：即使用户选的时刻不可行，也保留其策略结果，用文案与下表说明首末班
    service_briefing = build_plan_service_briefing(
        chosen, windows, start_minutes=query_time_minutes
    )
    meters = path_track_meters_by_line(chosen, graph)
    fare_yuan, notes = estimate_fare_yuan(fare_doc, meters)

    elapsed = time.perf_counter() - t0
    load_sec = t_after_load - t0
    plan_sec = elapsed - load_sec

    plan_dict = plan_to_serializable(
        chosen.objective_label,
        chosen.nodes,
        chosen.total_time_min,
        chosen.transfer_count,
        fare_yuan,
    )
    guide_text = generate_personalized_plan_guide(chosen, fare_yuan, guide_mode=guide_mode)
    if not ok_service and service_briefing.get("headline"):
        guide_text = guide_text + "\n\n" + str(service_briefing["headline"])
    if notes:
        guide_text = guide_text + "\n\n【票价估算说明】\n" + "\n".join(notes)

    return {
        "ok": True,
        "query": {"from": frm.strip(), "to": to.strip()},
        "resolved": {"from": start_station, "to": end_station},
        "strategy": strategy,
        "guide_mode": guide_mode,
        "elapsed_seconds": round(elapsed, 4),
        "load_seconds": round(load_sec, 4),
        "plan_seconds": round(plan_sec, 4),
        "plan": plan_dict,
        "service_time_check": {
            "ok": ok_service,
            "message": (
                "已通过简化首末班模型校验（演示）。"
                if ok_service
                else f"当前查询时刻下按模型不可行：{service_msg}"
            ),
            "query_hhmm": service_briefing.get("query_hhmm"),
            "headline": service_briefing.get("headline"),
            "lines": service_briefing.get("lines") or [],
        },
        "recommendation_reason": recommendation_reason,
        "alternatives": {
            "min_time": plan_to_serializable(
                plan_time.objective_label,
                plan_time.nodes,
                plan_time.total_time_min,
                plan_time.transfer_count,
                estimate_fare_yuan(fare_doc, path_track_meters_by_line(plan_time, graph))[0],
            ),
            "min_transfer": plan_to_serializable(
                plan_xfer.objective_label,
                plan_xfer.nodes,
                plan_xfer.total_time_min,
                plan_xfer.transfer_count,
                estimate_fare_yuan(fare_doc, path_track_meters_by_line(plan_xfer, graph))[0],
            ),
        },
        "alternatives_service_check": {
            "min_time": {"ok": ok_time, "message": msg_time or "可行"},
            "min_transfer": {"ok": ok_xfer, "message": msg_xfer or "可行"},
            "feasible_keys": feasible_keys,
        },
        "fare_notes": notes,
        "guide_text": guide_text,
    }


def subway_error_message(exc: Exception) -> str:
    if isinstance(exc, SubwayGuideError):
        return str(exc)
    return f"内部错误：{type(exc).__name__}: {exc}"
