# 数学二 RAG 知识库 — 完整参考示例

本文件记录2026-05-14建成的数学二知识库完整规格，作为「公式/演绎类知识库」构建模板。

## 总体规格

| 指标 | 值 |
|:-----|:----:|
| 文档数 | 15（13知识块 + 1公式速查 + 1知识图谱） |
| 总大小 | 228KB |
| 总造价 | ¥0.89 |
| 存储路径 | `/root/rag-data/math2_blocks/` |
| 搜索工具 | SimpleRAG（BM25关键词） |
| 研究策略 | Canonical知识优先（张宇/武忠祥/李永乐教材），BrightData仅验证source_url |

## 模块结构

| 模块 | 条数 | 文件 |
|:----|:----:|:-----|
| 高数上（极限/导数/积分/ODE） | 5 | limit_continuity / derivative / indefinite_integral / definite_integral / ode |
| 高数下（多元/二重/方法/易错） | 5 | multivariable_diff / double_integral / ode_application / solving_methods / mistakes |
| 线代（行列式矩阵/向量方程组/特征值二次型） | 3 | det_matrix / vector_equations / eigen_quadratic |
| 特殊文件（无17字段模板） | 2 | formula_cheatsheet（185条公式）+ knowledge_graph |

## 与技科类知识库的关键区别

数学知识库与408专业课（数据结构/操作系统/计算机网络）有以下不同，需要不同构建策略：

| 维度 | 技术类（OS/网络） | 数学类（数二） |
|:----|:-----------------|:--------------|
| 核心价值 | 概念+原理+最佳实践 | 公式+定理条件+计算步骤+易错点 |
| detailed_explanation | 含配置命令/代码示例 | 含典型例题+完整演算过程 |
| 来源 | 官方文档+技术博客 | 经典教材（张宇/武忠祥/李永乐） |
| 验证方式 | rag_search检索概念 | rag_search检索公式关键词 |
| 特殊模块 | 知识图谱 | 公式速查表（无17字段模板） |

## 关键决策

1. **公式速查表豁免17字段模板** — 数学公式不适合拆成17字段，直接以公式+简短说明格式存储，利于BM25关键词检索公式名
2. **易错点独立成块** — 数学的failure_cases非常丰富，专门用`math2_mistakes.txt`独立存储高频错误集，检索效率更高
3. **子Agent字段名问题** — 本次构建中子Agent使用了`key_points`/`formulas`/`exam_tips`等自创字段名而非标准的`core_concepts`/`keywords`/`best_practices`。不影响BM25召回但破坏一致性。后续应显式粘贴17字段名列表到子Agent prompt中
4. **解题方法单独成块** — `math2_solving_methods.txt`独立存储选填技巧/证明思路/计算规范，是该知识库最实用的部分
