将地铁出行手册、乘客守则等 PDF 放在本目录，然后在项目根目录执行：

  py -3 scripts/ingest_manual_pdfs.py

解析后的纯文本会写入 data/knowledge_text/，并与乘客规则 JSON 一并进入 LangChain RAG 向量索引。
索引会在知识库文件变更后自动重建（或重启 api_server）。
