"""
路径规划：最短时间（Dijkstra 按分钟）与最少换乘（字典序：换乘次数优先，时间次之）。
支持多起点、多终点（同站多线）。
"""

from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .network_graph import Edge, Node


@dataclass(frozen=True)
class PlanResult:
    """单套出行方案（一种优化目标下的结果）。"""

    objective_label: str
    start: Node
    end: Node
    nodes: list[Node]
    total_time_min: float
    transfer_count: int


def count_transfers_on_path(nodes: list[Node]) -> int:
    n = 0
    prev_line: str | None = None
    for line, _st in nodes:
        if prev_line is not None and line != prev_line:
            n += 1
        prev_line = line
    return n


def dijkstra_min_time(
    graph: dict[Node, list[Edge]],
    sources: Iterable[Node],
    goals: set[Node],
) -> PlanResult | None:
    """边权为 minutes，求总时间最短的方案。"""
    sources = list(sources)
    if not sources or not goals:
        return None

    dist: dict[Node, float] = {s: 0.0 for s in sources}
    prev: dict[Node, Node | None] = {s: None for s in sources}
    pq: list[tuple[float, Node]] = [(0.0, s) for s in sources]
    heapq.heapify(pq)

    best_goal: Node | None = None
    best_t = float("inf")

    while pq:
        d, u = heapq.heappop(pq)
        if d != dist.get(u, float("inf")):
            continue
        if u in goals and d < best_t:
            best_t = d
            best_goal = u
        if d > best_t:
            continue
        for e in graph.get(u, []):
            v: Node = (e.to_line, e.to_station)
            nd = d + e.minutes
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    if best_goal is None:
        return None

    path = _reconstruct(prev, best_goal)
    start_node = path[0]
    return PlanResult(
        objective_label="最短时间",
        start=start_node,
        end=best_goal,
        nodes=path,
        total_time_min=best_t,
        transfer_count=count_transfers_on_path(path),
    )


def dijkstra_min_transfer_then_time(
    graph: dict[Node, list[Edge]],
    sources: Iterable[Node],
    goals: set[Node],
) -> PlanResult | None:
    """
    字典序最小化 (换乘次数, 总时间分钟)。
    轨道边不增加换乘；换乘边换乘次数 +1。
    """
    sources = list(sources)
    if not sources or not goals:
        return None

    best: dict[Node, tuple[int, float]] = {s: (0, 0.0) for s in sources}
    prev: dict[Node, Node | None] = {s: None for s in sources}
    pq: list[tuple[int, float, Node]] = [(0, 0.0, s) for s in sources]
    heapq.heapify(pq)

    while pq:
        tc, tt, u = heapq.heappop(pq)
        if best.get(u) != (tc, tt):
            continue
        for e in graph.get(u, []):
            v: Node = (e.to_line, e.to_station)
            if e.kind == "track":
                nt, ntm = tc, tt + e.minutes
            else:
                nt, ntm = tc + 1, tt + e.minutes
            cand = (nt, ntm)
            old = best.get(v)
            if old is None or cand < old:
                best[v] = cand
                prev[v] = u
                heapq.heappush(pq, (nt, ntm, v))

    best_goal: Node | None = None
    best_pair: tuple[int, float] | None = None
    for g in goals:
        if g in best:
            if best_pair is None or best[g] < best_pair:
                best_pair = best[g]
                best_goal = g

    if best_goal is None or best_pair is None:
        return None

    path = _reconstruct(prev, best_goal)
    start_node = path[0]
    tr, tm = best_pair
    return PlanResult(
        objective_label="最少换乘",
        start=start_node,
        end=best_goal,
        nodes=path,
        total_time_min=tm,
        transfer_count=tr,
    )


def _reconstruct(prev: dict[Node, Node | None], goal: Node) -> list[Node]:
    path: list[Node] = []
    cur: Node | None = goal
    while cur is not None:
        path.append(cur)
        cur = prev.get(cur)
    path.reverse()
    return path


def path_track_distance_m(path: PlanResult, graph: dict[Node, list[Edge]]) -> int:
    total = 0
    for i in range(len(path.nodes) - 1):
        a, b = path.nodes[i], path.nodes[i + 1]
        tracks = [
            int(round(e.meters_if_track))
            for e in graph.get(a, [])
            if (e.to_line, e.to_station) == b and e.kind == "track"
        ]
        if tracks:
            total += tracks[0]
    return total


def path_track_meters_by_line(path: PlanResult, graph: dict[Node, list[Edge]]) -> dict[str, int]:
    acc: dict[str, int] = defaultdict(int)
    for i in range(len(path.nodes) - 1):
        a, b = path.nodes[i], path.nodes[i + 1]
        line = a[0]
        tracks = [
            int(round(e.meters_if_track))
            for e in graph.get(a, [])
            if (e.to_line, e.to_station) == b and e.kind == "track"
        ]
        if tracks:
            acc[line] += tracks[0]
    return dict(acc)
