"""注册与密码策略。"""

from __future__ import annotations

import re

_USERNAME_RE = re.compile(r"^[\u4e00-\u9fffA-Za-z0-9_]{3,20}$")
_PASSWORD_LEN = 8
_PASSWORD_HAS_LETTER = re.compile(r"[A-Za-z\u4e00-\u9fff]")
_PASSWORD_HAS_DIGIT = re.compile(r"\d")


class PolicyError(ValueError):
    """用户名校验或密码策略未通过。"""

    pass


def validate_username(username: str) -> str:
    s = (username or "").strip()
    if not s:
        raise PolicyError("用户名为空。")
    if not _USERNAME_RE.match(s):
        raise PolicyError(
            "用户名为 3–20 位，仅允许中文、英文、数字与下划线，不可含空格。"
        )
    return s


def validate_password_strength(password: str) -> str:
    p = password or ""
    if len(p) < _PASSWORD_LEN:
        raise PolicyError("密码至少 8 位。")
    if not _PASSWORD_HAS_LETTER.search(p) or not _PASSWORD_HAS_DIGIT.search(p):
        raise PolicyError("密码须同时包含至少一个字母或汉字与一位数字。")
    return p


def validate_register_passwords(p1: str, p2: str) -> str:
    a = validate_password_strength(p1)
    b = p2 or ""
    if a != b:
        raise PolicyError("两次输入的密码不一致。")
    return a
