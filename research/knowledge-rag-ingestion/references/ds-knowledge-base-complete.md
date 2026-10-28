# 数据结构知识库 — 完整参考示例

本文件记录2026-05-12建成的数据结构知识库完整规格，作为后续同类任务的参考模板。

## 总体规格

| 指标 | 值 |
|------|-----|
| 文档数 | 25（24知识块 + 1知识图谱） |
| 段落数 | 262 |
| 总大小 | 240KB |
| 总造价 | ¥0.32 |
| 存储路径 | `/root/rag-data/knowledge_blocks_v2/` |
| 搜索工具 | RAG SimpleRAG（BM25关键词） |
| 研究工具 | BrightData（搜索+抓取） |

## 模块结构

| 模块 | 条数 | 文件 | 来源数 |
|------|:----:|------|:------:|
| 线性表 | 3 | sequential_list / linked_list / compare | ≥2 |
| 栈与队列 | 2 | stack / queue | ≥2 |
| 树与二叉树 | 6 | btree_basics / traversal / bst / avl / heap / huffman | ≥2 |
| 图 | 5 | storage / traversal / mst / shortest_path / topo_critical | ≥3 |
| 查找 | 3 | search_basic / btree / hash | ≥2 |
| 排序 | 5 | insertion / exchange / selection / merge_radix / summary | ≥2 |
| 知识图谱 | 1 | knowledge_graph | — |

## 每条知识块的17个字段

按照 knowledge-rag-ingestion Skill 的 v2.0 规范，每条包含：

```
title             精确可检索中英文标题
summary           30-80字一句话总结
core_concepts     🔴 1-3句话提炼本质
detailed_explanation  800-2000字含代码示例
architecture_modules  🔴 存储结构+操作分类
keywords          20+中英文关键词
best_practices    6+条实战建议
limitations       4+条固有缺陷
common_problems   5+个常见问题
failure_cases     🔴 3+个易错场景
edge_cases        🔴 5+个边界条件
performance_bottlenecks  🔴 3+个性能瓶颈
related_concepts  5+个关联概念
source_url        ≥2个真实可信来源
confidence        4-5可信度评分
applicable_scenarios  🔴 5+个适用场景
embedding_text    300-500字高密度检索文本
```

## 构建流程回顾（最佳实践）

1. **Phase 1**: 先出研究计划 → 用户确认后进入Phase 2
2. **Phase 2**: BrightData搜索+抓取 ≥2个来源/条 → 交叉验证
3. **Phase 3**: delegate_task 3路并行 → 17字段打勾 → write_file到共享目录
4. **Phase 4**: 清空旧DB → `rm -f documents.json chunks.json && systemctl restart hermes-gateway` → 批量入库 → rag_search验证3方向 → 建知识图谱 → 可视化地图 → Token账单汇报

## 关键技术决策

- BM25关键词搜索（非向量搜索） → embedding_text要展开拼写特殊字符（如"B树"→"B树B-tree m阶"）
- mcp-compressor包装 → initialize响应必须含serverInfo
- BrightData优于openwebsearch（中文垂直内容）
- 子Agent必须有完整的17字段模板，否则会遗漏
