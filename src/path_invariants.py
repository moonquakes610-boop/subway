"""
路径结果不变量校验：用于调试与单元测试，保证「总时间」与图上边权累加一致。
"""

from __future__ import annotations

from .network_graph import Edge, Node
from .pathfinder import PlanResult


def path_edge_minutes_sum(nodes: list[Node], graph: dict[Node, list[Edge]]) -> float:
    """沿路径累加相邻顶点间边的 minutes（轨道+换乘）。"""
    if len(nodes) < 2:
        return 0.0
    total = 0.0
    for i in range(len(nodes) - 1):
        a, b = nodes[i], nodes[i + 1]
        cand = [
            float(e.minutes)
            for e in graph.get(a, [])
            if (e.to_line, e.to_station) == b
        ]
        if not cand:
            raise ValueError(f"路径在图上不连续：{a} -> {b}")
        # 与 Dijkstra 一致：同一对顶点间多条换乘/平行边时取最小边权
        total += min(cand)
    return total


def assert_plan_time_consistent(plan: PlanResult, graph: dict[Node, list[Edge]], eps: float = 1e-3) -> None:
    summed = path_edge_minutes_sum(plan.nodes, graph)
    if abs(summed - plan.total_time_min) > eps:
        raise AssertionError(
            f"时间不一致：边权和={summed:.4f} min，PlanResult.total_time_min={plan.total_time_min:.4f}"
        )
