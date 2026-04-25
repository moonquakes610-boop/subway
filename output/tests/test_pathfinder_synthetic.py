"""
合成路网：验证「最短时间」可能多换乘、「最少换乘」可能更慢。
运行：在项目根目录执行  python -m pytest tests/test_pathfinder_synthetic.py -q
或：python tests/test_pathfinder_synthetic.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.network_graph import Edge, Node  # noqa: E402
from src.pathfinder import (  # noqa: E402
    PlanResult,
    dijkstra_min_time,
    dijkstra_min_transfer_then_time,
)
from src.path_invariants import assert_plan_time_consistent, path_edge_minutes_sum  # noqa: E402


def _build_toy_graph() -> dict[Node, list[Edge]]:
    """
    N1--(X)--N2：100 min；N1--(Y)--N2：10 min；在 N1 可从 X 换乘到 Y（0 min 步行，计 1 次换乘）。
    仅从 (X,N1) 出发到 N2：最省时间应走 X->Y 换乘 + Y 上短区间；最少换乘应一直留在 X。
    """
    n1, n2 = "N1", "N2"
    lx, ly = "线X", "线Y"
    adj: dict[Node, list[Edge]] = {}

    def add_undirected(a: Node, b: Node, e_ab: Edge) -> None:
        rev = Edge(a[0], a[1], e_ab.kind, e_ab.meters_if_track, e_ab.minutes)
        adj.setdefault(a, []).append(e_ab)
        adj.setdefault(b, []).append(rev)

    add_undirected(
        (lx, n1),
        (lx, n2),
        Edge(lx, n2, "track", 1000.0, 100.0),
    )
    add_undirected(
        (ly, n1),
        (ly, n2),
        Edge(ly, n2, "track", 200.0, 10.0),
    )
    add_undirected(
        (lx, n1),
        (ly, n1),
        Edge(ly, n1, "transfer", 0.0, 0.0),
    )
    return adj


def test_toy_min_time_vs_min_transfer() -> None:
    g = _build_toy_graph()
    sources = [("线X", "N1")]
    goals = {("线X", "N2"), ("线Y", "N2")}

    pt = dijkstra_min_time(g, sources, goals)
    px = dijkstra_min_transfer_then_time(g, sources, goals)
    assert pt is not None and px is not None

    assert_plan_time_consistent(pt, g)
    assert_plan_time_consistent(px, g)

    assert pt.total_time_min < px.total_time_min
    assert pt.transfer_count > px.transfer_count

    assert path_edge_minutes_sum(pt.nodes, g) == 10.0
    assert px.transfer_count == 0
    assert abs(px.total_time_min - 100.0) < 1e-6


def test_disconnected_components() -> None:
    """两连通分量之间无路径，算法应返回 None。"""
    adj: dict[Node, list[Edge]] = {}

    def add_undirected(a: Node, b: Node, e_ab: Edge) -> None:
        rev = Edge(a[0], a[1], e_ab.kind, e_ab.meters_if_track, e_ab.minutes)
        adj.setdefault(a, []).append(e_ab)
        adj.setdefault(b, []).append(rev)

    add_undirected(("L", "S1"), ("L", "S2"), Edge("L", "S2", "track", 500, 2.0))
    add_undirected(("M", "T1"), ("M", "T2"), Edge("M", "T2", "track", 500, 2.0))

    assert dijkstra_min_time(adj, [("L", "S1")], {("M", "T2")}) is None
    assert dijkstra_min_transfer_then_time(adj, [("L", "S1")], {("M", "T2")}) is None


if __name__ == "__main__":
    test_toy_min_time_vs_min_transfer()
    test_disconnected_components()
    print("OK: synthetic pathfinder tests passed")
