"""领域异常类型：便于 CLI 统一捕获并输出清晰报错（验收：异常不崩溃）。"""


class SubwayGuideError(Exception):
    """地铁出行指南系统基础异常。"""


class DataValidationError(SubwayGuideError):
    """数据文件缺失、格式非法或清洗后不可用。"""


class StationNotFoundError(SubwayGuideError):
    """起点或终点无法匹配到唯一站点。"""


class RouteNotFoundError(SubwayGuideError):
    """路网中不存在连通路径。"""


class InputError(SubwayGuideError):
    """用户输入不合法（如空字符串）。"""
