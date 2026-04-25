"""
路径与数据目录配置。
默认以项目根目录（本文件上级目录的上一级）为基准，便于答辩时直接运行。
"""

import os
from pathlib import Path

# 测试用：在无 data 的临时目录下可将 SUBWAY_PROJECT_ROOT 指向空目录以验证「文件缺失」行为
_PROJECT_DEFAULT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = Path(os.environ.get("SUBWAY_PROJECT_ROOT", str(_PROJECT_DEFAULT))).resolve()
DATA_LUXIAN_DIR = PROJECT_ROOT / "data" / "luxian"
DATA_MAP_DIR = PROJECT_ROOT / "data" / "map"
# 乘车规章等公开文本知识库（与线路数据分离，便于扩展检索或 RAG）
DOCS_DIR = PROJECT_ROOT / "docs"

# 不参与普通路网里程累计、需单独计价的线路（与 fare_rules.json5 中名称一致）
SPECIAL_FARE_LINES = frozenset({"首都机场线", "大兴机场线", "西郊线"})

# 区间运行时间近似：按平均旅速由站间距折算分钟（答辩可说明：可与时刻表精细化替换）
AVERAGE_LINE_SPEED_KMH = 38.0
