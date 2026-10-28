# MCP RAG Server Evaluation

Evaluated during 2026-05-12 session. Result: **chose custom SimpleRAG over mcp-local-rag**.

## Candidate: mcp-local-rag (shinpr/mcp-local-rag)

⭐ 256 stars, 50 forks, 34 releases (latest v0.13.2, 2026-05-11)

**Pros:** npm-based, one-command setup (`npx -y mcp-local-rag`), hybrid search (semantic + keyword), LanceDB vector store, smart semantic chunking, fully local/private.

**Blockers for China deployment:**
1. Requires Node.js ≥22.12 (LXC 202 had v22.0.0 → upgraded to v22.13.0)
2. Transformers.js embedding model (~90MB) must download from HuggingFace on first use
3. HuggingFace is blocked in China even through Clash proxy and hf-mirror.com
4. muPDF-based PDF parser failed on Chinese PDFs (need to convert to TXT)

**Verdict:** Great software, but completely blocked by HuggingFace download requirement from China. Would work in non-China environments.

## Candidate: RAG-MCP (alejandro-ao/RAG-MCP)

⭐ 6 stars. Python-based, requires LlamaParse API key (extra cost + registration). Not evaluated in depth due to low activity and API dependency.

## Chosen: Custom SimpleRAG

**Architecture:** Python BM25 keyword search (no model/vectors needed), JSON file-based storage, custom MCP server.

**Rationale:** Zero external dependencies, works fully offline in China, no download/API costs, sufficient for technical document search where keyword precision matters.

**Trade-off:** No semantic/vector search (can't find "猫咪" when searching "猫"). Mitigated by Chinese keyword extraction in the tokenizer.
