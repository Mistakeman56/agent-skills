# 操作系统知识库 — 完整参考示例

本文件记录2026-05-14建成的操作系统知识库完整规格，作为408考研类知识库（已建立教材、认证标准明确的学科知识）的参考模板。

## 总体规格

| 指标 | 值 |
|------|-----|
| 文档数 | 22（21知识块 + 1知识图谱） |
| 段落数 | ~330 |
| 总大小 | 276KB |
| 总造价 | ¥0.91 |
| 存储路径 | `/root/rag-data/os_knowledge_blocks/` |
| 搜索工具 | RAG SimpleRAG（BM25关键词） |
| 研究工具 | 王道408教材（canonical）+ BrightData（来源URL验证） |
| 并发策略 | 3路delegate_task并行（8+5+8路） |

## 模块结构

| 模块 | 条数 | 文件名前缀 | 来源数 |
|------|:----:|:----------:|:------:|
| 概述 | 1 | os_overview | ≥2 |
| 进程管理 | 8 | os_process_* | ≥2 |
| 内存管理 | 5 | os_memory_* | ≥2 |
| 文件管理 | 4 | os_file_* / os_disk_* | ≥2 |
| I/O管理 | 3 | os_io_* | ≥2 |
| 知识图谱 | 1 | os_knowledge_graph | — |

## 文件命名约定

```
{domain}_{module}_{topic}.txt
```

示例：
```
os_process_sync_producer_consumer.txt  — 进程同步模块 → 生产者消费者问题
os_memory_noncontiguous.txt           — 内存管理模块 → 非连续分配
os_disk_schedule.txt                  — 文件管理模块 → 磁盘调度算法
```

## 每条知识块的17个字段

严格遵循 knowledge-rag-ingestion Skill 的 v2.0 规范，每条包含：

```
title             精确可检索中英文标题
summary           30-80字一句话总结
core_concepts     🔴 1-3句话提炼本质
detailed_explanation  800-2000字含伪代码示例
architecture_modules  🔴 存储结构+操作分类
keywords          20+中英文关键词
best_practices    6+条实战建议
limitations       4+条固有缺陷
common_problems   5+个常见问题
failure_cases     🔴 3+个易错场景（如银行家算法Need矩阵计算错误）
edge_cases        🔴 5+个边界条件（如所有请求同一柱面的磁盘调度）
performance_bottlenecks  🔴 3+个性能瓶颈
related_concepts  5+个关联概念
source_url        ≥2个真实可信来源
confidence        4-5可信度评分
applicable_scenarios  🔴 5+个适用场景
embedding_text    300-500字高密度检索文本
```

## 构建流程

### Phase 1：研究计划
- 基于408大纲拆分5大模块+知识图谱
- 优先级：进程管理(8) → 内存管理(5) → 文件管理(4) → I/O管理(3) → 概述(1)
- 输出 `research_plan.md` 给用户确认

### Phase 2：定向研究
- **关键区别（vs 技术类RAG）：** 408考研内容是高度标准化的教材知识，BrightData在此场景下的主要作用**不是发现新知识，而是获取source_url用于交叉验证**
- 后续同类任务（考研/认证考试）可直接采用「canonical知识为主 + BrightData为辅」策略
- BrightData搜索关键词示例：`"操作系统 进程管理 PV信号量 408考研"`

### Phase 3：知识蒸馏
- 21条知识块 → 3路delegate_task并行（进程管理8条 / 内存管理5条 / 文件+I/O+概述8条）
- **关键：每个子Agent的prompt必须包含完整17字段模板**，否则子Agent会在detailed_explanation上写得很详细但遗漏failure_cases/edge_cases等🔴字段
- 子Agent写文件到共享目录 `/root/rag-data/os_knowledge_blocks/`
- 执行耗时：~5分钟（3个Agent共约717秒）
- 验证：每个子Agent完成后应列出文件清单+字段完整性确认

### Phase 4：入库与验证
- 新增模块无需清空DB（仅替换旧版知识块时需要清空）
- 调用rag_ingest逐文件入库
- 验证策略：3个不同角度关键词，确保召回质量
  - `"银行家算法 死锁避免 安全序列"` → 验证死锁模块
  - `"页面置换算法 LRU FIFO CLOCK"` → 验证内存模块
  - `"生产者消费者 PV信号量 进程同步"` → 验证进程同步模块

### 费用报告参考
| 来源 | 输入(token) | 输出(token) |
|:----|:----------:|:----------:|
| 子Agent1 — 进程管理 | 336K | 21K |
| 子Agent2 — 内存管理 | 231K | 16K |
| 子Agent3 — 文件/I/O/概述 | 449K | 28K |
| 父Agent（研究+入库+验证） | ~200K | ~20K |
| **合计** | **~1,216K** | **~85K** |

**DeepSeek V4 Flash 成本：**
- 输入缓存命中 ~40%：~486K × ¥0.02/百万 = ¥0.01
- 输入缓存未命中 ~60%：~730K × ¥1/百万 = ¥0.73
- 输出：85K × ¥2/百万 = ¥0.17
- **总计：约¥0.91**

## 和数据结构知识库的对比

| 维度 | 数据结构 (DS) | 操作系统 (OS) |
|:----|:-------------:|:-------------:|
| 文档数 | 25 | 22 |
| 造价 | ¥0.32 | ¥0.91 |
| 并发策略 | 3路delegate_task | 3路delegate_task |
| 研究策略 | BrightData主搜+抓取 | Canonical教材主+ BrightData验证 |
| 特殊注意 | 模型对树/图结构理解偏差 | 伪代码/地址转换示例较多 |
| 知识类型 | 抽象数据结构 | 系统机制+策略+算法 |
