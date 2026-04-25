"""
边界与异常测试脚本（不依赖 pytest）。
在项目根目录：python scripts/run_boundary_tests.py
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _run_main(args: list[str]) -> tuple[int, str, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    failed = 0

    code, out, err = _run_main(["--from", "西单", "--to", "西单", "--no-regulations"])
    print(f"[同站] exit={code}")
    if code != 1 or ("相同" not in err and "相同" not in out):
        print("  FAIL: 期望退出码 1 且提示同站")
        failed += 1
    else:
        print("  PASS")

    code, out, err = _run_main(["--from", "___不存在的站名___", "--to", "西单", "--no-regulations"])
    print(f"[站名错误] exit={code}")
    if code != 2 or "未找到" not in err:
        print("  FAIL: 期望退出码 2 且 stderr 含未找到")
        failed += 1
    else:
        print("  PASS")

    code, out, err = _run_main(["--from", "   ", "--to", "西单", "--no-regulations"])
    print(f"[空起点] exit={code}")
    if code != 2 or "不能为空" not in err:
        print("  FAIL: 期望不能为空提示")
        failed += 1
    else:
        print("  PASS")

    with tempfile.TemporaryDirectory() as td:
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import os,sys; "
                f"os.environ['SUBWAY_PROJECT_ROOT']=r'{td}'; "
                f"sys.path.insert(0, r'{ROOT}'); "
                "from src.cli import main as m; "
                "sys.exit(m(['--from','西单','--to','圆明园','--no-regulations']))",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    print(f"[无 data 目录] exit={proc.returncode}")
    if proc.returncode not in (2, 3) or "[错误]" not in proc.stderr:
        print("  FAIL: 应有清晰错误", proc.stderr[:300])
        failed += 1
    else:
        print("  PASS")

    print("[无路径] 算法层见 tests/test_pathfinder_synthetic.py（全路网通常连通，CLI 难构造）")

    try:
        spec = importlib.util.spec_from_file_location(
            "tps",
            ROOT / "tests" / "test_pathfinder_synthetic.py",
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        mod.test_toy_min_time_vs_min_transfer()
        mod.test_disconnected_components()
        print("[合成算法] PASS")
    except Exception as e:
        print(f"[合成算法] FAIL: {e}")
        failed += 1

    from src.network_graph import nodes_at_station
    from src.pathfinder import dijkstra_min_time, dijkstra_min_transfer_then_time
    from src.path_invariants import assert_plan_time_consistent
    from src.persistent_cache import load_or_build_cached_network

    docs, meta, fare, g = load_or_build_cached_network()
    a, b = "上地软件园", "郭公庄"
    sa, sb = nodes_at_station(g, a), nodes_at_station(g, b)
    if sa and sb:
        pt = dijkstra_min_time(g, sa, set(sb))
        px = dijkstra_min_transfer_then_time(g, sa, set(sb))
        if pt and px:
            assert_plan_time_consistent(pt, g)
            assert_plan_time_consistent(px, g)
            print(
                f"[真实样例 {a}->{b}] 时间优: {pt.transfer_count} 换 {pt.total_time_min:.1f} min | "
                f"换乘优: {px.transfer_count} 换 {px.total_time_min:.1f} min | 同路径={pt.nodes == px.nodes}"
            )

    print(f"\n完成：失败 {failed} 项")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
