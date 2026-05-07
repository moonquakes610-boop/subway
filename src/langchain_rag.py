"""
LangChain RAG：从乘客规则、禁带目录与规章摘要中检索相关片段，并由 LLM 生成简短补充说明。

- 需配置 OPENAI_API_KEY（可选 OPENAI_BASE_URL 兼容代理或国内兼容端点）。
- 未配置或依赖缺失时自动跳过，不影响既有算法指南。
- 关闭：环境变量 BSG_LANGCHAIN=0
"""

from __future__ import annotations

import logging
import os
import threading

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

from .config import PROJECT_ROOT
from .reference_data import load_passenger_rules, load_prohibited_items
from .regulations import (
    regulatory_bullets_passenger_code,
    regulatory_prohibited_brief,
    regulatory_ticket_brief,
)

log = logging.getLogger(__name__)

_build_lock = threading.Lock()
_vectorstore: FAISS | None = None
_knowledge_fp: float | None = None

_REF_PASSENGER = PROJECT_ROOT / "data" / "reference" / "passenger_rules.json"
_REF_PROHIBITED = PROJECT_ROOT / "data" / "reference" / "prohibited_items.json"
_KNOWLEDGE_TEXT_DIR = PROJECT_ROOT / "data" / "knowledge_text"

MODE_LABELS_ZH: dict[str, str] = {
    "commute": "通勤",
    "tour": "游客",
    "senior": "老人或带娃",
    "rush": "赶时间",
}


def _knowledge_fingerprint() -> float:
    """随 JSON 规则与 pdf 入库文本变更而变，用于失效向量缓存。"""
    m = 0.0
    for p in (_REF_PASSENGER, _REF_PROHIBITED):
        if p.is_file():
            m = max(m, p.stat().st_mtime)
    if _KNOWLEDGE_TEXT_DIR.is_dir():
        for child in _KNOWLEDGE_TEXT_DIR.glob("*.txt"):
            if child.is_file():
                m = max(m, child.stat().st_mtime)
    return m


def reset_vectorstore_cache() -> None:
    """释放 FAISS 索引（知识库文件更新后或评测冷启动前调用）。"""
    global _vectorstore, _knowledge_fp
    with _build_lock:
        _vectorstore = None
        _knowledge_fp = None


def _load_ingested_txt_documents() -> list[Document]:
    """data/knowledge_text 下由 PDF 解析脚本生成的 .txt。"""
    docs: list[Document] = []
    if not _KNOWLEDGE_TEXT_DIR.is_dir():
        return docs
    for path in sorted(_KNOWLEDGE_TEXT_DIR.glob("*.txt")):
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if len(text) < 20:
            continue
        docs.append(
            Document(
                page_content=text,
                metadata={"source": "pdf_ingest", "file": path.name},
            )
        )
    return docs


def _langchain_env_enabled() -> bool:
    v = os.environ.get("BSG_LANGCHAIN", "1").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def _build_documents() -> list[Document]:
    docs: list[Document] = []
    pr = load_passenger_rules()
    for it in pr.get("items") or []:
        if not isinstance(it, dict):
            continue
        title = str(it.get("title") or "").strip()
        body = str(it.get("content") or "").strip()
        summ = str(it.get("summary") or "").strip()
        if not body:
            continue
        text = title + "\n" + (f"摘要：{summ}\n" if summ else "") + body
        docs.append(
            Document(
                page_content=text,
                metadata={"source": "passenger_rules", "id": str(it.get("id") or "")},
            )
        )
    ph = load_prohibited_items()
    for cat in ph.get("categories") or []:
        if not isinstance(cat, dict):
            continue
        label = str(cat.get("label") or cat.get("short_label") or "").strip()
        parts: list[str] = []
        if label:
            parts.append(label)
        for ex in cat.get("examples") or []:
            parts.append(str(ex))
        for item in cat.get("items") or []:
            parts.append(str(item))
        note = str(cat.get("note") or "").strip()
        if note:
            parts.append(note)
        blob = "\n".join(parts)
        if blob.strip():
            docs.append(
                Document(
                    page_content=blob,
                    metadata={"source": "prohibited_items", "id": str(cat.get("id") or "")},
                )
            )
    docs.append(
        Document(
            page_content="【车票规则摘要】" + regulatory_ticket_brief(),
            metadata={"source": "regulations", "id": "ticket"},
        )
    )
    docs.append(
        Document(
            page_content="【禁带品概括】" + regulatory_prohibited_brief(),
            metadata={"source": "regulations", "id": "prohibited_brief"},
        )
    )
    for i, b in enumerate(regulatory_bullets_passenger_code()):
        docs.append(
            Document(
                page_content="【乘客守则要点】" + b,
                metadata={"source": "regulations", "id": f"bullet_{i}"},
            )
        )
    extra = _load_ingested_txt_documents()
    if extra:
        log.info("LangChain：并入 PDF 入库文本 %d 条", len(extra))
    docs.extend(extra)
    return docs


def get_rag_vectorstore() -> FAISS:
    """供评测脚本与调试获取当前向量库。"""
    return _get_vectorstore()


def _get_vectorstore() -> FAISS:
    global _vectorstore, _knowledge_fp
    fp = _knowledge_fingerprint()
    with _build_lock:
        if _vectorstore is not None and _knowledge_fp == fp:
            return _vectorstore
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        base_url = os.environ.get("OPENAI_BASE_URL", "").strip() or None
        embed_model = os.environ.get("BSG_EMBED_MODEL", "text-embedding-3-small").strip()
        raw_docs = _build_documents()
        splitter = RecursiveCharacterTextSplitter(chunk_size=480, chunk_overlap=80)
        splits = splitter.split_documents(raw_docs)
        emb = OpenAIEmbeddings(
            model=embed_model,
            api_key=api_key,
            base_url=base_url,
        )
        log.info("LangChain：正在构建 FAISS 向量索引（%d 条切片）…", len(splits))
        _vectorstore = FAISS.from_documents(splits, emb)
        _knowledge_fp = fp
        return _vectorstore


def augment_guide_with_langchain(
    *,
    guide_text: str,
    guide_mode: str,
    from_station: str,
    to_station: str,
) -> str | None:
    """
    在算法生成的 guide_text 之外，追加一段基于检索摘录的 LLM 说明。
    不可用时返回 None。
    """
    if not _langchain_env_enabled():
        return None
    try:
        vs = _get_vectorstore()
        retriever = vs.as_retriever(search_kwargs={"k": 6})
        mode_zh = MODE_LABELS_ZH.get((guide_mode or "commute").strip().lower(), "通勤")
        question = (
            f"北京地铁从「{from_station}」到「{to_station}」，出行场景：{mode_zh}。"
            f"请检索与安检、携带物品、乘车秩序、应急与无障碍相关的规定。"
        )
        retrieved = retriever.invoke(question)
        context = "\n\n".join(
            f"[{d.metadata.get('source', '')}] {d.page_content}" for d in retrieved
        )
        llm = ChatOpenAI(
            model=os.environ.get("BSG_LLM_MODEL", "gpt-4o-mini").strip(),
            temperature=0.2,
            api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
            base_url=os.environ.get("OPENAI_BASE_URL", "").strip() or None,
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是北京地铁出行助手。只依据用户给出的「检索摘录」与「算法行程摘要」作答，"
                    "不要编造具体时刻表、票价数字或站点出入口。用简明中文分条列出（不超过 8 条短句），"
                    "侧重安检、携带物、文明乘车、紧急情况与无障碍关注；若摘录未涉及则不要臆测细节。",
                ),
                (
                    "human",
                    "【算法已生成的行程与提示摘要】\n{route}\n\n"
                    "【检索摘录】\n{context}\n\n"
                    "请写出对乘客的补充提示，不要重复逐站路线。",
                ),
            ]
        )
        chain = prompt | llm | StrOutputParser()
        out = chain.invoke(
            {
                "route": (guide_text or "")[:4000],
                "context": context,
            }
        )
        text = (out or "").strip()
        if not text:
            return None
        return "【RAG 智能补充（LangChain 检索 + 大模型）】\n" + text
    except Exception as e:
        log.warning("LangChain RAG 未执行或失败：%s", e)
        return None
