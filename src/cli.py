"""
命令行入口：数据加载与清洗、双目标路径规划、指南生成、结果导出。
验收：异常输入不崩溃；核心流程 INFO/ERROR 日志；清晰 stderr 报错。
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
import traceback
from pathlib import Path

from .data_loader import build_station_alias_index, resolve_station_query
from .errors import (
    InputError,
    RouteNotFoundError,
    StationNotFoundError,
    SubwayGuideError,
)
from .export_results import plan_to_serializable, write_json_report, write_text_report
from .fare import estimate_fare_yuan
from .guide_generator import generate_dual_plan_guide
from .logutil import get_logger, setup_logging
from .network_graph import nodes_at_station
from .pathfinder import dijkstra_min_time, dijkstra_min_transfer_then_time, path_track_meters_by_line
from .persistent_cache import load_or_build_cached_network
from .regulations import format_regulatory_appendix_merged

log = get_logger(__name__)


def _resolve_unique_station(
    raw: str,
    alias_index: dict[str, list[str]],
    role: str,
) -> str:
    q = raw.strip() if raw else ""
    if not q:
        raise InputError(f"{role}不能为空，请输入站点名称。")
    names = resolve_station_query(q, alias_index)
    if not names:
        raise StationNotFoundError(f"未找到与「{q}」匹配的站点，请检查拼写或换用数据中的规范站名。")
    if len(names) > 1:
        detail = "\n".join(f"  - {n}" for n in names)
        raise StationNotFoundError(
            f"「{q}」对应多个候选站点（{role}），请更精确输入：\n{detail}"
        )
    return names[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="北京地铁出行指南智能生成系统")
    parser.add_argument("--from", dest="frm", required=True, help="起点站名")
    parser.add_argument("--to", dest="to", required=True, help="终点站名")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="导出完整文字报告（UTF-8）",
    )
    parser.add_argument(
        "--export-json",
        type=Path,
        default=None,
        help="导出结构化 JSON（UTF-8）",
    )
    parser.add_argument(
        "--no-regulations",
        action="store_true",
        help="不附乘车规范与安全提示附录",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="出错时打印 Python 堆栈（调试用）",
    )
    parser.add_argument(
        "--rebuild-cache",
        action="store_true",
        help="忽略磁盘缓存并重新构建路网（数据更新后使用）",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="日志级别 DEBUG（默认 INFO）",
    )
    parser.add_argument(
        "--guide-mode",
        default="commute",
        choices=("commute", "tour", "senior", "rush"),
        help="出行场景（与 Web 一致；与 --langchain 联用）",
    )
    parser.add_argument(
        "--langchain",
        action="store_true",
        help="在已配置 OPENAI_API_KEY 时追加 LangChain RAG 补充段（需联网调用嵌入与聊天模型）",
    )
    args = parser.parse_args(argv)

    setup_logging(logging.DEBUG if args.verbose else logging.INFO)
    log.info("启动查询：%s -> %s", args.frm.strip(), args.to.strip())

    t0 = time.perf_counter()
    try:
        line_docs, metadata, fare_doc, graph = load_or_build_cached_network(
            force_rebuild=args.rebuild_cache,
        )
        t_after_load = time.perf_counter()
        log.info(
            "路网就绪：%d 条线路文档，%d 个图顶点，加载耗时 %.3fs",
            len(line_docs),
            len(graph),
            t_after_load - t0,
        )

        alias_index = build_station_alias_index(line_docs)
        start_station = _resolve_unique_station(args.frm, alias_index, "起点")
        end_station = _resolve_unique_station(args.to, alias_index, "终点")
        log.info("解析站名：%s -> %s", start_station, end_station)

        if start_station == end_station:
            log.info("起点与终点相同，跳过路径规划")
            print("[提示] 起点与终点相同，无需乘车。", file=sys.stderr)
            return 1

        sources = nodes_at_station(graph, start_station)
        goals = set(nodes_at_station(graph, end_station))
        if not sources:
            raise StationNotFoundError(
                f"起点「{start_station}」未出现在路网顶点中（数据可能未收录该站或清洗失败）。"
            )
        if not goals:
            raise StationNotFoundError(
                f"终点「{end_station}」未出现在路网顶点中（数据可能未收录该站或清洗失败）。"
            )

        log.info("开始路径规划：候选起点 %d 个，终点 %d 个", len(sources), len(goals))
        plan_time = dijkstra_min_time(graph, sources, goals)
        plan_xfer = dijkstra_min_transfer_then_time(graph, sources, goals)

        if plan_time is None or plan_xfer is None:
            log.error("规划失败：最短路或换乘优解为空（不连通或图异常）")
            raise RouteNotFoundError(
                "起点与终点在当前数据与换乘模型下不连通，或缺少换乘定义；请尝试其他站点。"
            )

        log.info(
            "最短时间方案：%.2f min，换乘 %d 次",
            plan_time.total_time_min,
            plan_time.transfer_count,
        )
        log.info(
            "最少换乘方案：%.2f min，换乘 %d 次",
            plan_xfer.total_time_min,
            plan_xfer.transfer_count,
        )

        meters_t = path_track_meters_by_line(plan_time, graph)
        meters_x = path_track_meters_by_line(plan_xfer, graph)
        fare_t, notes_t = estimate_fare_yuan(fare_doc, meters_t)
        fare_x, notes_x = estimate_fare_yuan(fare_doc, meters_x)

        guide_body = generate_dual_plan_guide(
            plan_time,
            plan_xfer,
            fare_t,
            fare_x,
            start_station,
            end_station,
        )
        appendix = ""
        if not args.no_regulations:
            appendix = "\n\n" + format_regulatory_appendix_merged(
                plan_time.nodes,
                plan_xfer.nodes,
                include_accessibility=True,
            )

        fare_block = (
            "\n\n【票价估算明细 — 方案 A：最短时间】\n"
            + "\n".join(notes_t)
            + "\n\n【票价估算明细 — 方案 B：最少换乘】\n"
            + "\n".join(notes_x)
            + "\n"
        )

        full_text = guide_body + appendix + fare_block
        if args.langchain:
            try:
                from .langchain_rag import augment_guide_with_langchain

                rag_extra = augment_guide_with_langchain(
                    guide_text=guide_body[:4500],
                    guide_mode=args.guide_mode,
                    from_station=start_station,
                    to_station=end_station,
                )
                if rag_extra:
                    full_text = full_text + "\n\n" + rag_extra
            except ImportError:
                log.warning("未安装 LangChain 依赖，已跳过 --langchain（请 pip install -r requirements.txt）")

        elapsed = time.perf_counter() - t0
        load_sec = t_after_load - t0
        plan_sec = elapsed - load_sec
        print(full_text)
        print()
        detail = f"加载路网 {load_sec:.2f}s + 规划与生成 {plan_sec:.2f}s = 合计 {elapsed:.2f}s"
        if elapsed > 2.0:
            print(
                f"[耗时] {detail}（验收建议合计 ≤2 秒；首次构建缓存会较慢，之后见「加载路网」应显著下降）",
                file=sys.stderr,
            )
        else:
            print(f"[耗时] {detail}", file=sys.stderr)

        if args.out is not None:
            try:
                write_text_report(args.out, full_text)
                log.info("已导出文本：%s", args.out.resolve())
                print(f"[导出] 文本：{args.out.resolve()}", file=sys.stderr)
            except OSError as e:
                log.error("导出文本失败：%s", e)
                print(f"[错误] 无法写入文本文件：{e}", file=sys.stderr)
                return 4

        if args.export_json is not None:
            try:
                payload = {
                    "query": {"from": args.frm.strip(), "to": args.to.strip()},
                    "resolved_stations": {"from": start_station, "to": end_station},
                    "elapsed_seconds": round(elapsed, 4),
                    "plans": [
                        plan_to_serializable(
                            plan_time.objective_label,
                            plan_time.nodes,
                            plan_time.total_time_min,
                            plan_time.transfer_count,
                            fare_t,
                        ),
                        plan_to_serializable(
                            plan_xfer.objective_label,
                            plan_xfer.nodes,
                            plan_xfer.total_time_min,
                            plan_xfer.transfer_count,
                            fare_x,
                        ),
                    ],
                    "fare_notes": {
                        "最短时间": notes_t,
                        "最少换乘": notes_x,
                    },
                    "same_route": plan_time.nodes == plan_xfer.nodes,
                }
                write_json_report(args.export_json, payload)
                log.info("已导出 JSON：%s", args.export_json.resolve())
                print(f"[导出] JSON：{args.export_json.resolve()}", file=sys.stderr)
            except OSError as e:
                log.error("导出 JSON 失败：%s", e)
                print(f"[错误] 无法写入 JSON 文件：{e}", file=sys.stderr)
                return 4

        log.info("查询成功，总耗时 %.3fs", elapsed)
        return 0

    except SubwayGuideError as e:
        log.error("业务异常：%s", e)
        print(f"[错误] {e}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        log.error("数据或 IO 异常：%s", e)
        print(f"[错误] 文件或数据解析失败：{e}", file=sys.stderr)
        return 3
    except Exception as e:
        log.error("未预期异常：%s: %s", type(e).__name__, e)
        print(f"[错误] 未预期异常：{type(e).__name__}: {e}", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 99


if __name__ == "__main__":
    raise SystemExit(main())
