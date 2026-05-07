"""
仅将 data/luxian 同步到 app.db 中的 sys_* 镜像表，不启动 Web。

用法（项目根目录）:
    py -3 scripts/sync_system_mirror.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.system_data_mirror import sync_mirrored_system_tables, mirror_summary


def main() -> int:
    sync_mirrored_system_tables()
    for k, v in sorted(mirror_summary().items()):
        print(f"  {k} = {v}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
