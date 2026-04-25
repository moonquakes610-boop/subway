"""
插入答辩演示用账号（若用户名已存在则跳过）。

默认：用户名 demo  密码：Beijing1

用法（项目根）:
    py -3 scripts/seed_demo_user.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import auth_db
from src.auth_passwords import hash_password


def main() -> int:
    auth_db.ensure_db()
    u = "demo"
    p = "Beijing1"
    if auth_db.get_user_by_username(u):
        print("用户 demo 已存在，未修改。", flush=True)
        return 0
    h = hash_password(p)
    uid = auth_db.create_user(u, h)
    print(f"已创建演示用户：{u} / {p}  （id={uid}）", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
