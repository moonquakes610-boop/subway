"""bcrypt 密码哈希与校验。"""

from __future__ import annotations

import bcrypt as _bcrypt


def hash_password(plain: str) -> str:
    b = (plain or "").encode("utf-8")
    return _bcrypt.hashpw(b, _bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(plain: str, stored_hash: str) -> bool:
    try:
        return _bcrypt.checkpw(
            (plain or "").encode("utf-8"),
            (stored_hash or "").encode("ascii"),
        )
    except (ValueError, TypeError):
        return False
