"""
RAG 轻量评测：索引构建耗时、检索关键词命中率、（可选）端到端生成耗时。
结果写入 output/rag_eval_report.txt，便于论文「测试与性能」章节引用。

用法（需 OPENAI_API_KEY）：
    py -3 scripts/eval_rag_benchmark.py
    py -3 scripts/eval_rag_benchmark.py --with-llm

不加 --with-llm 时不调用聊天模型，节省费用。
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

OUTPUT_REPORT = ROOT / "output" / "rag_eval_report.txt"

# (检索问句, 期望在检索结果文本中至少出现其一的关键词列表)
RETRIEVAL_CASES: list[tuple[str, list[str]]] = [
    ("地铁安检和液体携带要注意什么", ["安检", "液体", "查验"]),
    ("车厢里能否吸烟或使用电子烟", ["吸烟", "电子烟"]),
    ("携带宠物或活禽有什么限制", ["活禽", "动物", "宠物", "导盲"]),
    ("行李尺寸或重量有什么要求", ["千克", "米", "行李", "携带"]),
    ("遇到突发事件乘客应怎么做", ["突发事件", "指挥", "疏散", "冷静"]),
]


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="RAG 基准评测")
    parser.add_argument(
        "--with-llm",
        action="store_true",
        help="包含一次完整 LLM 生成（产生 API 费用）",
    )
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY", "").strip():
        print("未设置 OPENAI_API_KEY，跳过评测。", file=sys.stderr)
        return 1

    from src.langchain_rag import (
        augment_guide_with_langchain,
        get_rag_vectorstore,
        reset_vectorstore_cache,
    )

    lines: list[str] = []
    lines.append("RAG 轻量评测报告（本地脚本生成）")
    lines.append(f"OPENAI_BASE_URL={os.environ.get('OPENAI_BASE_URL', '') or '(默认)'}")
    lines.append("")

    reset_vectorstore_cache()
    t0 = time.perf_counter()
    vs = get_rag_vectorstore()
    t_build = time.perf_counter() - t0
    lines.append(f"冷启动构建 FAISS 索引：{t_build:.3f} s")

    t1 = time.perf_counter()
    _ = get_rag_vectorstore()
    t_warm = time.perf_counter() - t1
    lines.append(f"热路径再次获取索引：{t_warm:.3f} s")
    lines.append("")

    retriever = vs.as_retriever(search_kwargs={"k": 6})
    hits = 0
    for question, kws in RETRIEVAL_CASES:
        docs = retriever.invoke(question)
        blob = "\n".join(d.page_content for d in docs)
        ok = any(kw in blob for kw in kws)
        if ok:
            hits += 1
        lines.append(f"检索 [{question[:24]}…] 关键词命中：{'是' if ok else '否'} （关键词 {kws}）")
    rate = hits / len(RETRIEVAL_CASES) if RETRIEVAL_CASES else 0.0
    lines.append("")
    lines.append(f"检索用例命中率：{hits}/{len(RETRIEVAL_CASES)} = {rate:.0%}")
    lines.append("（说明：为论文可用的粗粒度指标；精细评测需人工标注或标准问答集。）")
    lines.append("")

    if args.with_llm:
        t2 = time.perf_counter()
        out = augment_guide_with_langchain(
            guide_text="【测试】西单 → 圆明园，最短时间方案演示。",
            guide_mode="commute",
            from_station="西单",
            to_station="圆明园",
        )
        t_llm = time.perf_counter() - t2
        lines.append(f"端到端 RAG+LLM 单次耗时：{t_llm:.3f} s")
        lines.append(f"生成非空：{'是' if (out and len(out) > 20) else '否'}")
    else:
        lines.append("未使用 --with-llm，跳过端到端 LLM 耗时。")

    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    report_body = "\n".join(lines) + "\n"
    OUTPUT_REPORT.write_text(report_body, encoding="utf-8")
    print(report_body, flush=True)
    print(f"已写入：{OUTPUT_REPORT.relative_to(ROOT)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
