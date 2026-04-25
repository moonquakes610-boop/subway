"""登录防暴力：同一 IP+用户名 短时间失败过多次则锁一段时间。"""

from __future__ import annotations

import time
from typing import Any

# (失败次数, 锁截止 unix 时间)
_state: dict[str, dict[str, Any]] = {}
_FAIL_WINDOW = 600.0  # 10 分钟内计数
_MAX_FAILS = 5
_LOCK_SECONDS = 900.0  # 15 分钟


def _now() -> float:
    return time.time()


def check_locked(key: str) -> str | None:
    """若被锁定返回原因文案，否则 None。锁期结束后清空失败次数。"""
    s = _state.get(key)
    if not s:
        return None
    until = s.get("lock_until") or 0.0
    if _now() < until:
        left = int(until - _now()) + 1
        return f"尝试次数过多，请约 {max(1, left // 60)} 分后再试。"
    s.pop("lock_until", None)
    s["times"] = []
    s["fails"] = 0
    return None


def record_fail(key: str) -> str | None:
    """记录一次失败；若触发锁定返回提示，否则 None。"""
    t = _now()
    s = _state.setdefault(key, {"times": []})
    times: list[float] = s.setdefault("times", [])
    times.append(t)
    # 只保留窗口内
    cut = t - _FAIL_WINDOW
    s["times"] = [x for x in times if x >= cut]
    s["fails"] = len(s["times"])
    if s["fails"] >= _MAX_FAILS:
        s["lock_until"] = t + _LOCK_SECONDS
        return "登录失败次数过多，已暂时锁定 15 分钟。请稍后再试。"
    return None


def clear_fails(key: str) -> None:
    _state.pop(key, None)
