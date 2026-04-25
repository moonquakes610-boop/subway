"""
清空问题反馈表（仅 feedback，不影响用户与历史）。

适用：管理后台刚上线却看到大量「待处理」反馈 —— 通常是本机
data/auth/app.db 里**以前测试/开发/脚本**写入的数据，不是程序随机生成的假数据。

用法（项目根）:
    py -3 scripts/clear_feedback.py
    # 或先备份再删:
    # copy data\\auth\\app.db data\\auth\\app.db.bak
    # py -3 scripts\\clear_feedback.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "auth" / "app.db"


def main() -> int:
    if not DB.is_file():
        print("未找到数据库：", DB, flush=True)
        return 1
    n = 0
    with sqlite3.connect(DB) as conn:
        cur = conn.execute("SELECT COUNT(*) FROM feedback")
        n = int(cur.fetchone()[0] or 0)
        conn.execute("DELETE FROM feedback")
        conn.commit()
    print(f"已删除 feedback 表共 {n} 条记录。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
