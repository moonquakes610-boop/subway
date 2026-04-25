"""统一日志配置：核心流程打 INFO，失败打 ERROR（输出到 stderr，便于与标准结果分离）。"""

from __future__ import annotations

import logging
import sys
from typing import TextIO


def setup_logging(level: int = logging.INFO, stream: TextIO | None = None) -> None:
    """
    初始化根日志（幂等：避免重复 addHandler）。
    level: logging.INFO / logging.DEBUG / logging.ERROR 等
    """
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(levelname)s [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
