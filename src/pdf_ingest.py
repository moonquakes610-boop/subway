"""
地铁出行手册类 PDF → 纯文本：解析、清洗，供 RAG 向量索引使用。

流程：放入 data/knowledge_pdf_in/*.pdf → 运行 scripts/ingest_manual_pdfs.py
→ 生成 data/knowledge_text/*.txt（与 JSON 规则库一并被 langchain_rag 索引）。
"""

from __future__ import annotations

import re
from pathlib import Path

from .config import PROJECT_ROOT

KNOWLEDGE_PDF_IN = PROJECT_ROOT / "data" / "knowledge_pdf_in"
KNOWLEDGE_TEXT_OUT = PROJECT_ROOT / "data" / "knowledge_text"


def clean_extracted_text(raw: str) -> str:
    """去噪：统一换行、压缩空白、去掉明显页眉页脚孤立数字行（保守）。"""
    if not raw:
        return ""
    t = raw.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t\f\v]+", " ", t)
    lines = []
    for line in t.split("\n"):
        s = line.strip()
        if not s:
            lines.append("")
            continue
        if re.fullmatch(r"-\s*\d+\s*-", s) or re.fullmatch(r"\d{1,4}", s):
            continue
        lines.append(s)
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def extract_pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        if txt.strip():
            parts.append(txt)
    return clean_extracted_text("\n\n".join(parts))


def ingest_pdf_directory(
    pdf_dir: Path | None = None,
    out_dir: Path | None = None,
) -> list[Path]:
    """
    扫描目录下所有 .pdf，写出同名 .txt 到输出目录。
    返回已写入的文件路径列表。
    """
    pdf_dir = pdf_dir or KNOWLEDGE_PDF_IN
    out_dir = out_dir or KNOWLEDGE_TEXT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if not pdf_dir.is_dir():
        return written
    for pdf in sorted(pdf_dir.glob("*.pdf")):
        if not pdf.is_file():
            continue
        try:
            body = extract_pdf_text(pdf)
        except Exception:
            continue
        if not body:
            continue
        out_path = out_dir / f"{pdf.stem}_from_pdf.txt"
        out_path.write_text(
            f"【来源 PDF：{pdf.name}】\n\n{body}",
            encoding="utf-8",
        )
        written.append(out_path)
    return written
