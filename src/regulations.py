"""
规章与无障碍信息摘要模块。

数据来源：项目 docs/ 目录下的公开文本 txt（《乘客守则》《禁止携带物品目录》
《车票使用规则》《无障碍服务地点》等）。出行前请以运营方与交通主管部门最新公布为准。

本模块为后续向量检索 / RAG 预留结构化入口；当前为基于摘要与本地文件的轻量引用。
"""

from __future__ import annotations

from pathlib import Path

from .config import DOCS_DIR

ACCESSIBILITY_TXT = DOCS_DIR / "无障碍服务地点.txt"


def _read_text_flexible(path: Path) -> str:
    """优先 UTF-8，失败则尝试 GBK（Windows 导出的 txt 常见）。"""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def ordered_unique_stations_along_path(station_sequence: list[tuple[str, str]]) -> list[str]:
    """沿乘车顺序去重站名（不含线路名）。"""
    seen: set[str] = set()
    out: list[str] = []
    for _line, st in station_sequence:
        if st not in seen:
            seen.add(st)
            out.append(st)
    return out


def lookup_accessibility_rows(station_name: str, doc_path: Path | None = None, max_rows: int = 2) -> list[str]:
    """
    在《无障碍服务地点》表中按「车站名称」列精确匹配行（制表符分隔）。
    同站可能出现在多条线路表中，返回至多 max_rows 行原文。
    """
    path = doc_path or ACCESSIBILITY_TXT
    if not path.is_file():
        return []
    hits: list[str] = []
    for line in _read_text_flexible(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("残疾人预约电话"):
            continue
        if "车站名称" in stripped and "召援" in stripped:
            continue
        if stripped.endswith("无障碍服务设施表") or stripped.endswith("无障碍服务设施表\r"):
            continue
        parts = stripped.split("\t")
        if len(parts) < 2:
            continue
        if parts[0].strip() == station_name:
            hits.append(stripped)
            if len(hits) >= max_rows:
                break
    return hits


def regulatory_bullets_passenger_code() -> list[str]:
    """《北京市轨道交通乘客守则》核心条款摘要（非全文）。"""
    return [
        "进入车站出入口、通道、站厅、站台和列车车厢的人员，均应遵守《乘客守则》。",
        "按规定购票乘车，禁止使用伪造、变造票卡；配合安全检查，拒检者可能被拒绝进站。",
        "携带物品重量不得超过 30 千克，长度不得超过 1.8 米，宽和高均不得超过 0.5 米；"
        "不得携带妨碍通行或可能影响运营安全的电动代步工具（无障碍用途电动轮椅除外）。",
        "1.3 米以下儿童应在成人陪同下乘车；醉酒、衣冠不整等可能影响秩序者不得进站。",
        "候车排队、禁止越过安全线；乘车先下后上；终点站须全部下车；列车停运时服从工作人员疏散。",
        "禁止擅自进入轨道隧道、强行扒门、非紧急动用安全装置、在疏散通道堆放物品等行为。",
        "车厢内禁止进食（婴儿、病人除外）；禁止吸烟（含电子烟）、携带活禽猫狗（警犬、导盲犬除外）、"
        "外放音乐、推销等；车站车厢禁止使用滑板车、轮滑、携带充气气球进站等（详见守则全文）。",
        "应自觉为老幼病残孕等让座；爱护设施，突发事件时服从指挥有序疏散。",
    ]


def regulatory_ticket_brief() -> str:
    """《车票使用规则》要点摘要。"""
    return (
        "除首都机场线、大兴机场线外，实行计程限时票制；起步 6 公里（含）内 3 元，按里程递增；"
        "一次行程在付费区内最多可停留 4 小时。定期票、一卡通、电子票等购票与充值方式见规则全文。"
    )


def regulatory_prohibited_brief() -> str:
    """《禁止携带物品目录》高度概括（详细类别以公安机关与目录原文为准）。"""
    return (
        "禁止携带枪支弹药、爆炸物品、管制器具及具有杀伤力的器具、易燃易爆品、毒害品、腐蚀性物品、"
        "放射性物品、传染病病原体，以及可能危害公共安全或行车安全的物品等。"
    )


def format_regulatory_appendix(
    path_nodes: list[tuple[str, str]],
    include_accessibility: bool = True,
) -> str:
    """
    生成可附在出行指南后的「规范与安全提示」段落。
    path_nodes: 与 PlanResult.nodes 相同，list[tuple[str,str]]（线路名, 站名）
    """
    lines: list[str] = []
    lines.append("—— 乘车规范与安全提示（摘要，摘自公开文本）——")
    lines.append("以下内容为便于阅读的摘录，不构成法律意见；请以北京市交通委员会及运营企业最新公布为准。")
    lines.append("")
    lines.append("【车票与计时】" + regulatory_ticket_brief())
    lines.append("")
    lines.append("【禁止携带】" + regulatory_prohibited_brief())
    lines.append("")
    lines.append("【乘客守则要点】")
    for b in regulatory_bullets_passenger_code():
        lines.append(f"- {b}")

    if include_accessibility:
        stations = ordered_unique_stations_along_path(path_nodes)
        lines.append("")
        lines.append("【无障碍设施（表中摘录）】残疾人预约电话：010-96165。")
        shown = 0
        for st in stations:
            rows = lookup_accessibility_rows(st, max_rows=1)
            if not rows:
                continue
            lines.append(f"- 「{st}」：{rows[0]}")
            shown += 1
            if shown >= 8:
                lines.append("- … 更多站点请查阅 docs/无障碍服务地点.txt …")
                break

    lines.append("")
    lines.append("全文请参阅项目 docs/ 目录内对应 txt 文件。")
    return "\n".join(lines)


def format_regulatory_appendix_merged(
    *path_nodes_chunks: list[tuple[str, str]],
    include_accessibility: bool = True,
) -> str:
    """合并多套方案经过的站点序列，再生成附录（无障碍摘录覆盖更多途经站）。"""
    merged: list[tuple[str, str]] = []
    for chunk in path_nodes_chunks:
        merged.extend(chunk)
    return format_regulatory_appendix(merged, include_accessibility=include_accessibility)
