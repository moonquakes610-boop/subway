"""
将 data/knowledge_pdf_in 下的 PDF 解析为纯文本，写入 data/knowledge_text，
供 LangChain RAG 与论文「PDF 处理流程」描述使用。

用法（项目根目录）：
    py -3 scripts/ingest_manual_pdfs.py

依赖：pip install pypdf（见 requirements.txt）
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pdf_ingest import KNOWLEDGE_PDF_IN, KNOWLEDGE_TEXT_OUT, ingest_pdf_directory


def main() -> int:
    written = ingest_pdf_directory()
    if not written:
        print(
            f"未生成新文件。请将 PDF 放入：{KNOWLEDGE_PDF_IN}\n"
            f"输出目录：{KNOWLEDGE_TEXT_OUT}",
            flush=True,
        )
        return 0
    print(f"已写入 {len(written)} 个文本文件：", flush=True)
    for p in written:
        print(f"  - {p.relative_to(ROOT)}", flush=True)
    print("提示：重启 api_server 或等待下次查询时，向量索引会随文件变更自动重建。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
