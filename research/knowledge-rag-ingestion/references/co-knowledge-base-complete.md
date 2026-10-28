# 计算机组成原理知识库 — 完整参考示例

本文件记录2026-05-18建成的计算机组成原理（CO）知识库完整规格，作为408考研类知识库（第4个学科、已知教材、标准化大纲）的参考模板。

## 总体规格

| 指标 | 值 |
|------|-----|
| 文档数 | 27（26知识块 + 1知识图谱 + 1易错集） |
| 段落数 | ~650 |
| 总大小 | ~250KB |
| 总造价 | ¥0.87 |
| 存储路径 | `/root/rag-data/co_knowledge_blocks/` |
| 搜索工具 | RAG SimpleRAG（BM25关键词） |
| 研究工具 | Canonical教材（王道408 + 汤小丹《计算机组成原理》） |
| BrightData可用性 | ❌ 不可用 → 仅使用canonical知识 |
| 并发策略 | 3路delegate_task并行（7+6+14路），第三路600s超时 |
| 前一路耗时 | 287s（7条）|
| 第二路耗时 | 337s（6条）|
| 第三路耗时 | 600s超时（计划14条，实际完成10条）|

## 模块结构

| 模块 | 条数 | 文件名前缀 | 备注 |
|------|:----:|:----------:|:----:|
| 计算机系统概述 | 1 | `co_overview_*` | 冯·诺依曼 + 性能指标 |
| 数据表示与运算 | 6 | `co_data_*` + `co_alu_*` | 最高优先级（选择题必考） |
| 存储系统 | 6 | `co_mem_*` + `co_cache_*` + `co_disk_*` | 大题常客（Cache计算） |
| 指令系统 | 4 | `co_isa_*` | 含MIPS范例 |
| 中央处理器CPU | 6 | `co_cpu_*` + `co_pipeline_*` | 最难点（流水线每年必出大题） |
| 总线与I/O | 3 | `co_bus_*` + `co_io_*` + `co_interrupt` | |
| 知识图谱 | 1 | `co_knowledge_graph` | 模块关联 + 学习路径 + 命题规律 |
| 易错集 | 1 | `co_mistakes_collection` | 高频易错题汇总 |

## 与OS知识库的对比

| 维度 | 操作系统 (OS) | 计算机组成原理 (CO) |
|:----|:-------------:|:------------------:|
| 文档数 | 22 | 27 |
| 造价 | ¥0.91 | ¥0.87 |
| 并发策略 | 3路delegate_task | 3路delegate_task |
| 最大子Agent负载 | 8条 | 14条 ← ⚠️ 失败！超时了 |
| BrightData | OK（获取source_url） | ❌ 不可用（纯canonical） |
| 特殊注意 | 伪代码/地址转换示例 | 流水线forwarding是408大题考点，detailed_explanation要最深入 |

## 构建流程关键决策

### Phase 1：研究计划
- 基于408大纲拆分为6大模块 + 知识点 + 易错集共27条
- 通过分析OS知识库的构建经验，预估¥1.20（实际¥0.87）
- 输出 `research_plan.md` 给用户确认

### Phase 2：定向研究
- BrightData MCP不可用 → 直接走canonical教材策略
- **验证：** 对于高度标准化的教材知识（考研408），即使BrightData不可用，canonical知识蒸馏也完全可行
- 输出 `research_notes.md` 记录来源计划

### Phase 3：知识蒸馏
- 27条 → 3路delegate_task并行

#### ⚠️ 子Agent负载极限
| 路由 | 条数 | 结果 | 耗时 |
|:----|:----:|:----:|:----:|
| 数据表示+概述 | 7 | ✅ 完成 | 287s |
| 存储系统 | 6 | ✅ 完成 | 337s |
| 指令+CPU+总线IO+知识图谱 | **14** | ❌ **600s超时** | 仅完成10条 |

**教训：** 14条对一个子Agent来说太多了。600s超时下约能完成10条（每条约60s），剩余4条需要补跑。
**建议负载上限：** 单子Agent ≤10条（安全）/ ≤8条（稳定可靠）
如果是detailed_explanation要求800-2000字的复杂知识点（如pipeline_hazard），更应限制在 ≤6条

#### 超时恢复策略
当子Agent超时时，先检查目标目录已写入哪些文件：
```bash
ls /root/rag-data/co_knowledge_blocks/co_*.txt | wc -l
```
如果大部分已生成，只补写缺失的文件即可。本案例中14条计划，10条已完成，缺失的是流水线3条和知识图谱1条，由父Agent直接用write_file补上。

### Phase 4：入库与验证

**批量入库（非MCP rag_ingest逐条调用的方法）：**
```python
from simple_rag import SimpleRAG
import glob, os
rag = SimpleRAG()
files = sorted(glob.glob('co_knowledge_blocks/co_*.txt'))
for f in files:
    rag.ingest(f)
print(f'Done! Total docs: {len(rag.documents)}, Total chunks: {len(rag.chunks)}')
```
这种方法比通过MCP工具逐条调用快很多（27条秒级完成 vs MCP逐条可能数分钟）。

**验证策略（3个不同角度关键词）：**
```python
rag.search("Cache 组相联映射 替换算法 LRU", top_k=3)     # → 命中 co_cache_basics.txt
rag.search("流水线 数据冒险 前递 forwarding", top_k=3)    # → 命中 co_pipeline_hazard.txt
rag.search("IEEE754 浮点数 单精度 规格化", top_k=3)       # → 命中 co_data_float_ieee754.txt
```

### 费用报告

| 来源 | 输入(token) | 输出(token) |
|:----|:----------:|:----------:|
| 子Agent1 — 数据表示+概述（7条） | 315K | 17.5K |
| 子Agent2 — 存储系统（6条） | 313K | 22K |
| 子Agent3 — 指令+CPU+总线IO+图谱（10/14条，超时） | ~400K | ~30K |
| 父Agent（研究+入库+验证+补缺失） | ~115K | ~18K |
| **合计** | **~1,143K** | **~87.5K** |

**DeepSeek V4 Flash 成本：**
- 输入缓存命中 ~40%：~457K × ¥0.02/百万 = ¥0.01
- 输入缓存未命中 ~60%：~686K × ¥1/百万 = ¥0.69
- 输出：87.5K × ¥2/百万 = ¥0.18
- **总计：约¥0.87**

## 与DS/OS/计网/数二/英语知识库的整合

截至2026-05-18，已完成408四科的全部知识库：

| 学科 | 条数 | 造价 |
|:----|:----:|:----:|
| 数据结构 (DS) | 49 | ¥0.32 |
| 计算机组成原理 (CO) | 27 | ¥0.87 |
| 操作系统 (OS) | 22 | ¥0.91 |
| 计算机网络 (CN) | 21 | ¥0.83 |
| 数学二 | 15 | ¥0.89 |
| 英语 | 34 | ¥1.10 |
| **合计** | **168** | **~¥4.92** |

## 使用

CO知识库已集成到SimpleRAG，通过MCP工具 `rag_search` 可跨库检索所有学科。搜索时关键词建议包含学科前缀以缩小范围，如 `"计组 Cache 组相联"`、`"CO 流水线 数据冒险"`。
