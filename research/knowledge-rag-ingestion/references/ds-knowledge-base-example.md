# 数据结构知识库 — 完整构建实例

这是一个按照完整17字段规格构建的408考研数据结构知识库实例。
规模：25个文档 / 262个段落 / 240KB / ¥0.32总造价

## 领域划分

| 模块 | 文件数 | 示例文件 |
|------|:------:|----------|
| 线性结构 | 3 | ds_sequential_list_v2.txt, ds_linked_list_v2.txt, ds_compare_v2.txt |
| 栈与队列 | 2 | ds_stack_v2.txt, ds_queue_v2.txt |
| 树与二叉树 | 6 | ds_btree_basics_v2.txt ~ ds_huffman_v2.txt |
| 图 | 5 | ds_graph_storage_v2.txt ~ ds_topo_critical_v2.txt |
| 查找 | 3 | ds_search_basic_v2.txt, ds_btree_v2.txt, ds_hash_v2.txt |
| 排序 | 5 | ds_sort_insertion_v2.txt ~ ds_sort_summary_v2.txt |
| 知识图谱 | 1 | ds_knowledge_graph.txt |

## 每条知识块的17个字段示例（取自 ds_stack_v2.txt）

```
title: 栈(Stack) — 顺序栈·链栈·共享栈·LIFO原理与应用       ✅
summary: 栈是一种受限的线性表...                            ✅
core_concepts: 栈的核心思想是限制数据访问点...               ✅
detailed_explanation: 含三份完整C代码（顺序栈/链栈/共享栈）   ✅
architecture_modules: 存储结构(顺序/链式/共享) + 操作类别    ✅
keywords: 栈, stack, LIFO, 顺序栈, 链栈, 共享栈... 25+个    ✅
best_practices: 6条实战建议                                 ✅
limitations: 4条固有缺陷                                    ✅
common_problems: 5个常见问题                                ✅
failure_cases: 栈溢出/栈下溢/共享栈空间竞争                   ✅
edge_cases: 空栈出栈/满栈入栈/负数取模/单个元素/大递归深度   ✅
performance_bottlenecks: 扩容代价/动态分配/共享栈增长不均衡  ✅
related_concepts: 队列, 双端队列, 单调栈, 递归, DFS...      ✅
source_url: https://zhuanlan.zhihu.com/p/686085302          ✅
confidence: 4                                               ✅
applicable_scenarios: 10个（编译器/浏览器/编辑器/DFS...）     ✅
embedding_text: 300+字高密度检索文本                         ✅
```

## 构建流程（可复用模板，推荐用v2.0方式）

### 推荐流程（v2.0 — 从计算机组成原理构建中验证）
当知识块数量超过10条时：

```
1. 输出 research_plan.md（知识树+优先级+预计条数）
2. 用 BrightData 搜索各子领域，收集来源URL
3. 输出 research_notes.md（来源URL+可信度+核心发现）
4. delegate_task 分发（max_concurrent_children=3）
   → 子Agent prompt中必须包含17字段模板！！！
   → 子Agent输出的source_url必须≥2个
   → 告诉子Agent目标文件名和保存目录
5. 等待所有子Agent完成（如果超时，手动补全）
6. 构建知识图谱（ds_knowledge_graph.txt / cn_knowledge_graph.txt）
7. 逐条 rag_ingest 入库
8. rag_search 验证召回（3个不同角度的关键词）
9. 出Token账单（参考Skill中的Token Cost章节）
10. 可选：excalidraw 可视化地图
```

### 成功案例：计算机组成原理（v2.0流程，验证通过）

| 步骤 | 说明 |
|:----|:------|
| 研究者计划 | ✅ research_plan.md（19条，7大模块） |
| BrightData研究 | ✅ 4轮搜索，收集中科院/CSDN/知乎等16+来源 |
| 研究笔记 | ✅ research_notes.md（来源+可信度） |
| 并行生成 | ✅ 3路子Agent，每路6条，全部完成无超时 |
| 17字段 | ✅ 全部包含，含failure_cases（Pentium FDIV等历史事故）|
| 多来源 | ✅ 每条≥2个source_url |
| 知识图谱 | ✅ 跨领域关联+408大题关联 |
| 入库 | ✅ 19文件 → 311段落 |
| 验证 | ✅ 最高召回分2.02（Cache） |
| Token账单 | ✅ 精确到子Agent级别 |

### 成本参考
| 场景 | 输入 | 输出 | 总费用 |
|:----|:----:|:----:|:------:|
| 中等规模(~19条, 计组) | ~722K | ~69K | ¥0.58 |
| 大规模(~24条, 数据结构v2) | ~946K | ~53K | ¥0.20 |
| 子Agent单路典型消耗 | 190-260K | 19-25K | ¥0.15-0.21 |

## 注意事项
1. 子Agent如果超时（600s），手动补全该子领域的知识块
2. 入库前如替换旧版知识，须清空旧DB（删json文件+重启gateway）
3. 最后必须验证召回（rag_search至少3个不同角度的关键词）
4. 知识图谱作为最后一条入库，用于跨领域关联检索
5. 最终可用 excalidraw 生成可视化地图，提高用户体验
6. 子Agent prompt中**必须携带17字段模板**，否则子Agent会遗漏字段
7. 子Agent生成的source_url尽量≥2个，如只有1个需补全
