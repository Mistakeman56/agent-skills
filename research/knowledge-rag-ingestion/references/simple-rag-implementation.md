# SimpleRAG Implementation Reference

## Overview

当前RAG知识库使用的是本地BM25关键词搜索方案（无需下载任何embedding模型）。部署在LXC 202上。

## Files

| 文件 | 路径 | 说明 |
|------|------|------|
| SimpleRAG类 | `/root/rag-data/simple_rag.py` | 核心RAG实现（BM25搜索+语义chunk） |
| MCP服务器 | `/root/rag-data/rag_mcp_server.py` | MCP协议包装（tools/list, tools/call） |
| 数据库 | `/root/rag-data/db/documents.json` | 文档元数据 |
| 数据库 | `/root/rag-data/db/chunks.json` | 知识块数据（含关键词索引） |
| 数据目录 | `/root/rag-data/` | 文档存放目录 |
| Hermes配置 | `~/.hermes/config.yaml` → `mcp_servers.simple-rag` | MCP服务器注册 |

## SimpleRAG Python API

```python
from pathlib import Path
sys.path.insert(0, '/root/rag-data')
from simple_rag import SimpleRAG

rag = SimpleRAG()  # 自动加载 /root/rag-data/db/

# 导入文档（TXT/MD/PDF）
rag.ingest("/path/to/file.txt")

# 搜索（返回按相关度排序的结果）
results = rag.search("ARP欺骗如何攻击", top_k=3)

# 查看状态
rag.status()    # {"documents": N, "chunks": N}
rag.list_files()  # [{"filename": "xxx", "text_len": N}, ...]
```

## Search Algorithm

BM25-like scoring:
1. 提取查询中的中文(>=2字)和英文(>=3字符)关键词
2. 计算每个chunk的关键词匹配数 / (chunk长度/100 + 1)
3. 精确短语匹配 → 分数x2
4. 文件名匹配 → 分数x1.5
5. 按分数降序返回top_k

## MCP Protocol

标准JSON-RPC 2.0 over stdio:

```json
// Request (stdin):
{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}

// Response (stdout):
{"jsonrpc":"2.0","id":1,"result":{"tools":[...]}}

// Tool call:
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"rag_search","arguments":{"query":"ARP欺骗","top_k":3}},"id":2}
```

## Deployment Notes

- 首次配置后需重启gateway（`systemctl restart hermes-gateway`）
- `/reload-mcp` 仅在CLI/TUI平台可用，微信平台需完整重启
- 如出现 `CancelledError`，增加config中的`timeout: 120`
- MCP服务器启动必须快：用lazy import避免初始化时加载PyPDF2等重量级模块
