"""
初始化/校验 SQLite 用户库（在 data/auth/ 下创建 app.db 与表结构）。

用法（项目根目录）:
    py -3 scripts/init_auth_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.auth_db import DB_PATH, ensure_db


def main() -> int:
    ensure_db()
    print(f"数据库就绪：{DB_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
