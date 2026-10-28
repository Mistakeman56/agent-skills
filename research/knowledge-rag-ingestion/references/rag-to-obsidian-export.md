# RAG 知识库 → Obsidian Vault 导出方案

## 背景

用户的 SimpleRAG 知识库中有 141+ 个结构化知识块（数据结构49/OS22/计网21/数二15/英语34/金融4），格式为 .txt，内容结构化为17字段模板。

用户想把这些知识能在 MacBook 上用 Obsidian 查看、双链、图谱化。

## 现状

| 环节 | 已有工具 | 缺什么 |
|:----|:---------|:-------|
| 知识采集 | `knowledge-rag-ingestion` pipeline ✅ | — |
| 知识存储 | SimpleRAG (BM25) + `/root/rag-data/` ✅ | — |
| 知识检索 | MCP `rag_search` 工具 ✅ | — |
| 知识导出 | ✅ **方案A已执行**（详见下方执行记录） | — |

## 执行记录（2026-05-18）

**实际产出：** 187 篇 Obsidian Markdown 笔记 / 7 大学科 / 3.1MB

| 学科 | 笔记数 | 源文件 |
|:----|:------:|:-------|
| 01-数据结构 | 25 | /root/rag-data/knowledge_blocks_v2/ds_*.txt |
| 02-数学二 | 15 | /root/rag-data/math2_blocks/math2_*.txt |
| 03-计组 | 27 | /root/rag-data/co_knowledge_blocks/co_*.txt |
| 04-操作系统 | 22 | /root/rag-data/os_knowledge_blocks/os_*.txt |
| 05-计网 | 21 | /root/rag-data/cn_network_blocks/cn_*.txt |
| 06-考研英语 | 34 | /root/rag-data/english_blocks/eng_*.txt |
| 07-金融知识 | 41 | /root/rag-data/fin_blocks/*.txt + finance_knowledge_blocks/blk_*.txt |

**执行策略：** 3路 delegate_task 并行，每路负责2-3个学科
- Agent 1: 数据结构(25) + 数学二(15) = 40篇 ✅
- Agent 2: 计组(27) + 计网(21) = 48篇 ✅
- Agent 3: OS(22) + 英语(34) + 金融(41) = 97篇 ✅

**耗时：** ~440秒（3路并行）
**额外产出：** 跨学科总关联图 1篇（408-四科关联图.md）+ Vault README 首页

### 转换模板（已验证可执行）

每条 17 字段 .txt → 以下结构的 .md：

```markdown
---
title: "{{title}}"
tags: [{{学科}}, {{模块}}]
aliases: ["{{英文名}}"]
created: 2026-05-18
subject: {{学科}}
source: "{{source_url}}"
confidence: {{confidence}}
---

# {{title}}

> {{summary}}

## 核心概念
{{core_concepts}}

## 详细说明
{{detailed_explanation}}

## 知识结构
| 维度 | 内容 |
|------|------|
| 存储结构 | ... |
| 操作类别 | ... |

## 最佳实践
- ✅ {{best_practice_1}}
- ✅ {{best_practice_2}}

## ⚠️ 易错场景
- ⚠️ {{failure_case_1}}

## 边界条件
- 🔲 {{edge_case_1}}

## 适用场景
- 👉 {{scenario_1}}

## 关联知识点
- [[相关概念1]]
- [[相关概念2]]

## 关键词
`{{keywords}}`
```

### 特殊处理规则
1. **词汇类**（eng_vocab_*.txt）→ 豁免标准模板，保留紧凑列表格式，仅加YAML frontmatter
2. **作文模板类**（eng_writing_*.txt）→ 同上，保留模板格式
3. **公式速查类**（math2_formula_cheatsheet.txt）→ 豁免标准模板，原样保留
4. **易错题集**（*_mistakes_collection.txt）→ 用标准模板但强调列表渲染
5. **知识图谱**（*_knowledge_graph.txt）→ 转为 MOC 索引笔记（学科目录导航用）

### 关键设计决策

1. **学科即文件夹** — Obsidian 用目录结构区分学科，比打标签更直观
2. **每个知识块一个文件** — 不要合并，给双链制最细粒度
3. **MOC 索引文件** — 每学科一个 `知识图谱.md` 列出所有笔记，方便导航
4. **双向链接自动生成** — 从 `keywords` + `related_concepts` 字段提取，跨学科链接手动补充
5. **emoji callout** — ⚠️易错/🔲边界/⚡性能瓶颈/🔴限制/✅最佳实践/❓常见问题/👉适用场景
6. **architecture_modules** — 有则渲染为 Markdown 表格，无则跳过整段
7. **embedding_text** — 跳过（仅用于RAG向量检索，不放在Obsidian里）
8. **YAML frontmatter** — 含 title/tags/aliases/created/subject/source/confidence

## 跨学科链接策略（已验证）

每种学科的笔记尾部追加跨学科 `[[wikilink]]`：

### 计组 ↔ 其他
- [[Cache]] ↔ [[页面置换算法]]（OS）
- [[TLB]] ↔ [[虚拟内存]]（OS）
- [[中断]] ↔ [[系统调用]]（OS）

### 数据结构 ↔ 其他
- [[栈]] ↔ [[函数调用栈帧]]（OS）
- [[B树]] ↔ [[文件索引结构]]（OS）
- [[图]] ↔ [[路由算法]]（计网）

### OS ↔ 其他
- [[虚拟内存]] ↔ [[Cache]] + [[主存扩展]]（计组）
- [[文件系统]] ↔ [[B树]]（数据结构）
- [[进程通信]] ↔ [[传输层端口]]（计网）

### 计网 ↔ 其他
- [[路由算法]] ↔ [[图]]（数据结构）
- [[校验码]] ↔ [[CRC]]（计组）

## 增量更新策略

Vault 生成后，后续新增知识块只需：
1. 将新 .txt 文件写入对应学科目录
2. 在父Agent中调用转换函数（写 .md 到 obsidian-vault/ 对应文件夹）
3. 更新该学科的 MOC 索引文件
4. 如果涉及新概念，更新 408-四科关联图.md

## 导出方案

### 方案A：自建转换脚本（推荐）

写一个 Python 脚本，读取所有知识块目录下的 .txt 文件，逐条转成 Obsidian 格式 .md：

```python
转换逻辑:
  1. 遍历 /root/rag-data/*_blocks/*.txt
  2. 解析17字段结构 → YAML frontmatter + markdown body
  3. 按学科分文件夹（数据结构/OS/计网/数二/英语）
  4. 自动生成 [[双向链接]]
     - 从 keywords/related_concepts 中提取
     - 每篇笔记尾部的 "## 关联知识" 列表
  5. 生成索引文件 MOC (Map of Content)
  6. 输出到 /root/rag-data/obsidian-vault/
```

### 方案B：Obsidian Local REST API

1. MacBook 上 Obsidian 装 **Local REST API** 插件
2. Hermes 通过 HTTP API 推送新笔记
3. 适合增量更新（学一课推一条）

### 方案C：obsidian-web

用 Node.js 架一个 HTTP 服务，Hermes 可以通过 API 把 RAG 内容推送进去。

## 知识块 → Obsidian 格式映射

```
原始 .txt 格式 (17字段):
  title: ...
  summary: ...
  core_concepts: ...
  detailed_explanation: ...
  keywords: [A, B, C]
  related_concepts: [X, Y, Z]
  ...

转换为 .md:
---
title: "线性表"
tags: [数据结构, 线性表, 顺序表, 链表]
keywords: [sequential_list, linked_list]
aliases: [顺序表, 链表]
---

# 线性表

## 一句话总结
{{summary}}

## 核心概念
{{core_concepts}}

## 详细说明
{{detailed_explanation}}

## 最佳实践
- {{best_practice_1}}
- {{best_practice_2}}

## 关联知识
- [[顺序表]]
- [[链表]]
- [[栈]]

## 易错点
- {{failure_case_1}}
```

## 关键设计决策

1. **学科即文件夹** — Obsidian 用目录结构区分学科，比打标签更直观
2. **每个知识块一个文件** — 不要合并，给双链制最细粒度
3. **MOC 索引文件** — 每学科一个 `索引.md` 列出所有笔记，方便导航
4. **双向链接自动生成** — 从 `keywords` + `related_concepts` 字段提取
5. **增量更新** — 只跑新增/修改的文件，不重写全部

## Obsidian 插件推荐（配合使用）

| 插件 | 用途 |
|:----|:-----|
| **Smart Notes** | 用户在小红书看到的，自动生成摘要+关联 |
| **Local REST API** | Hermes 远程推送笔记 |
| **Graph Analysis** | 内置功能，查看知识图谱 |
| **Excalidraw** | 画知识结构图（用户已有excalidraw文件） |
