"""
将线路与换乘数据构造成「(线路, 站名)」为顶点的图。

边属性：
- 轨道边：站间距（米）+ 按平均旅速折算的运行时间（分钟）
- 换乘边：换乘步行时间（分钟，来自 metadata），里程为 0

路径规划：
- 「最短时间」：边权统一为 minutes，Dijkstra
- 「最少换乘」：先最小化换乘次数，同换乘次数下最小化总时间（字典序 Dijkstra）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import AVERAGE_LINE_SPEED_KMH


@dataclass(frozen=True)
class Edge:
    to_line: str
    to_station: str
    kind: str  # "track" | "transfer"
    meters_if_track: float  # 换乘边为 0
    minutes: float  # 轨道：运行时间；换乘：步行时间


Node = tuple[str, str]  # (line_name, station_name)


def _track_travel_minutes(distance_m: float, speed_kmh: float = AVERAGE_LINE_SPEED_KMH) -> float:
    """站间距离（米）→ 运行时间（分钟），匀速近似。"""
    if distance_m <= 0:
        return 0.0
    km_h = speed_kmh
    if km_h <= 0:
        raise ValueError("AVERAGE_LINE_SPEED_KMH 必须为正")
    return (distance_m / 1000.0) / km_h * 60.0


def _transfer_minutes(
    rules: list[dict[str, Any]],
    from_line: str,
    to_line: str,
) -> float | None:
    candidates: list[float] = []
    for r in rules:
        if r.get("from") != from_line or r.get("to") != to_line:
            continue
        candidates.append(float(r["minutes"]))
    if not candidates:
        return None
    return min(candidates)


def build_graph(
    line_docs: list[dict[str, Any]],
    metadata: dict[str, Any],
    speed_kmh: float = AVERAGE_LINE_SPEED_KMH,
) -> dict[Node, list[Edge]]:
    from .data_loader import station_segments_for_line

    adj: dict[Node, list[Edge]] = {}

    def add_edge(a: Node, b: Node, edge_ab: Edge) -> None:
        rev = Edge(
            to_line=a[0],
            to_station=a[1],
            kind=edge_ab.kind,
            meters_if_track=edge_ab.meters_if_track,
            minutes=edge_ab.minutes,
        )
        adj.setdefault(a, []).append(edge_ab)
        adj.setdefault(b, []).append(rev)

    for doc in line_docs:
        line_name, segments = station_segments_for_line(doc)
        for u, v, dist in segments:
            n1: Node = (line_name, u)
            n2: Node = (line_name, v)
            d = float(dist)
            mins = _track_travel_minutes(d, speed_kmh)
            add_edge(
                n1,
                n2,
                Edge(n2[0], n2[1], "track", d, mins),
            )

    transfers: dict[str, Any] = metadata.get("transfers", {})
    for station, rules in transfers.items():
        lines_at_station = {ln for ln, st in adj if st == station}
        for la in lines_at_station:
            for lb in lines_at_station:
                if la == lb:
                    continue
                tm = _transfer_minutes(rules, la, lb)
                if tm is None:
                    continue
                add_edge(
                    (la, station),
                    (lb, station),
                    Edge(lb, station, "transfer", 0.0, float(tm)),
                )

    return adj


def nodes_at_station(graph: dict[Node, list[Edge]], station: str) -> list[Node]:
    lines = {ln for ln, st in graph if st == station}
    return sorted((ln, station) for ln in lines)


def all_stations(graph: dict[Node, list[Edge]]) -> set[str]:
    return {st for _, st in graph}
