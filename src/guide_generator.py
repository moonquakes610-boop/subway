"""
智能文字指南生成：基于路径结构化信息生成可读中文说明。
支持多套方案并列展示（最短时间 vs 最少换乘）。
"""

from __future__ import annotations

from .pathfinder import PlanResult

GuideMode = str


def path_to_legs(path: PlanResult) -> list[tuple[str, list[str]]]:
    """将 (线路, 站) 序列合并为乘车段。"""
    legs: list[tuple[str, list[str]]] = []
    cur_line: str | None = None
    cur_stations: list[str] = []
    for line, st in path.nodes:
        if cur_line is None:
            cur_line = line
            cur_stations = [st]
        elif line == cur_line:
            cur_stations.append(st)
        else:
            legs.append((cur_line, cur_stations))
            cur_line = line
            cur_stations = [st]
    if cur_line is not None:
        legs.append((cur_line, cur_stations))
    return legs


def _append_leg_lines(lines_out: list[str], legs: list[tuple[str, list[str]]]) -> None:
    for idx, (line_name, sts) in enumerate(legs, start=1):
        seg_n = len(sts) - 1
        if idx == 1:
            lines_out.append(
                f"{idx}. 在「{sts[0]}」乘坐 {line_name}，经过 {seg_n} 个区间，到达「{sts[-1]}」。"
            )
        else:
            lines_out.append(
                f"{idx}. 在「{sts[0]}」换乘 {line_name}，经过 {seg_n} 个区间，到达「{sts[-1]}」。"
            )
        if len(sts) <= 6:
            lines_out.append(f"   途经站点：{' → '.join(sts)}")
        else:
            head = " → ".join(sts[:3])
            tail = " → ".join(sts[-3:])
            lines_out.append(f"   途经站点（节选）：{head} → … → {tail}")


def generate_single_plan_guide(
    path: PlanResult,
    total_fare_yuan: int,
    header_title: str | None = "【出行方案】",
) -> str:
    """为单套方案生成文字说明。"""
    legs = path_to_legs(path)
    lines_out: list[str] = []
    if header_title:
        lines_out.append(header_title)
    lines_out.append(
        f"优化目标：{path.objective_label}。"
        f"模型估算全程约 {path.total_time_min:.1f} 分钟（含换乘步行），换乘 {path.transfer_count} 次；"
        f"估算票价约 {total_fare_yuan} 元（演示）。"
    )
    lines_out.append("—— 乘车步骤 ——")
    _append_leg_lines(lines_out, legs)
    lines_out.append("—— 提示 ——")
    lines_out.append("时间按站间距与平均旅速近似，换乘时间来自公开换乘数据；请以现场时刻表为准。")
    lines_out.append("请留意首末班车与出入口信息；路径为算法推荐，请以现场标识与官方 App 为准。")
    return "\n".join(lines_out)


def _guide_mode_tips(guide_mode: GuideMode, path: PlanResult) -> list[str]:
    mode = (guide_mode or "commute").strip().lower()
    tips: list[str] = []
    if mode == "rush":
        tips.append("你当前偏向“赶时间”场景：优先按车门附近候车，换乘时尽量靠近出站方向。")
        if path.transfer_count >= 3:
            tips.append("当前方案换乘较多，若携带行李建议在时间可接受时减少换乘。")
    elif mode == "senior":
        tips.append("你当前偏向“老人/带娃”场景：建议优先使用电梯，预留更充裕的换乘与步行时间。")
        if path.transfer_count >= 2:
            tips.append("该路线换乘次数不低，可在非高峰时段出行以降低拥挤风险。")
    elif mode == "tour":
        tips.append("你当前偏向“游客”场景：建议提前确认景点最近出入口，避免站内绕行。")
        tips.append("如需拍照或停留，请留意站台安全线与客流秩序。")
    else:
        tips.append("你当前偏向“通勤”场景：建议结合实时客流与到站信息，动态调整候车位置。")

    if path.total_time_min >= 60:
        tips.append("预计行程较长，建议预留 10-15 分钟机动时间。")
    return tips


def generate_personalized_plan_guide(
    path: PlanResult,
    total_fare_yuan: int,
    guide_mode: GuideMode = "commute",
) -> str:
    text = generate_single_plan_guide(path, total_fare_yuan, header_title="【智能出行指南】")
    tips = _guide_mode_tips(guide_mode, path)
    if not tips:
        return text
    return text + "\n\n【场景化建议】\n" + "\n".join(f"- {t}" for t in tips)


def generate_dual_plan_guide(
    plan_time: PlanResult,
    plan_transfer: PlanResult,
    fare_time: int,
    fare_transfer: int,
    start_name: str,
    end_name: str,
) -> str:
    """
    生成包含「最短时间」与「最少换乘」两套方案对比的完整指南正文（不含规章附录与票价明细表）。
    """
    parts: list[str] = []
    parts.append("【地铁出行指南】（系统自动生成）")
    parts.append(f"行程：「{start_name}」→「{end_name}」")
    parts.append("")
    parts.append("════════ 方案 A：优先「最短时间」 ════════")
    parts.append(generate_single_plan_guide(plan_time, fare_time, header_title=None))
    parts.append("")
    parts.append("════════ 方案 B：优先「最少换乘」 ════════")
    parts.append(generate_single_plan_guide(plan_transfer, fare_transfer, header_title=None))
    if plan_time.nodes == plan_transfer.nodes:
        parts.append("")
        parts.append("（说明：两套方案路径一致。）")
    return "\n".join(parts)
