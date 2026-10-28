---
name: knowledge-rag-ingestion
description: "Use when: 1) 用户要求调研/研究某个技术领域并存入RAG知识库; 2) 用户发来文档要求整理入库; 3) 回答中发现知识缺口需自动补全。执行四阶段Pipeline：Research Planning → Targeted Research → Knowledge Distillation → Memory Optimization，产出高质量结构化知识块导入SimpleRAG向量数据库。"
version: 2.0.0
author: Hermes Agent + <PASSWORD>
license: MIT
metadata:
  hermes:
    tags: [rag, knowledge-base, research, pipeline, vector-database, simple-rag]
    related_skills: [native-mcp]
---

# ⛔ 预检清单（必须逐条确认后再开始！）

**AI容易犯的错（每次执行前读一遍！）：**
1. ❌ **不加载Skill直接写** → 必须先 `skill_view('knowledge-rag-ingestion')`
2. ❌ **看一次就扔一边** → 每完成一个步骤，回来再看一眼checklist
3. ❌ **过度自信赶进度** → 用户说"快干吧"也要先出研究计划，不要跳阶段
4. ❌ **子Agent没有模板** → 发给子Agent的prompt里必须包含完整17字段模板
5. ❌ **不产研究文档** → `research_plan.md` 和 `research_notes.md` 必须输出
6. ❌ **忘记多源共识** → 每条知识块需要≥2个可信来源，source_url填满
7. ❌ **子Agent自己发明字段名** → prompt里只说"17字段模板"不够，子Agent会自己编字段名（key_points/formulas/exam_tips），必须逐行贴出17个准确字段名

**读完上面这7条再继续往下看！**

# Knowledge RAG Ingestion Pipeline

## Overview

将零散的技术文章、文档、调研成果转化为**高质量、结构化、可检索的RAG知识库**。核心原则：**宁缺毋滥**——每个知识块必须独立、完整、聚焦单一主题、经过AI理解后重写。禁止直接存储原始网页、大段原文或低质量长文本。

**目标：** 构建一个具备专业级理解、长期记忆、精准召回、持续成长能力的AI专家系统。

**参考模板：** `skill_view('knowledge-rag-ingestion', 'references/ds-knowledge-base-complete.md')` 查看已完成的数据结构知识库完整规格（25文档/262段落/17字段/多源/知识图谱），作为同类任务的构建模板。  \\n**408考研模板：** `skill_view('knowledge-rag-ingestion', 'references/os-knowledge-base-complete.md')` 查看已完成的操作系统知识库规格（22文档~330段落/¥0.91/3路并行/canonical知识策略），作为考研/认证考试类知识库的构建模板。  \\n**用户场景知识库模板：** `skill_view('knowledge-rag-ingestion', 'references/cn-network-knowledge-base-complete.md')` 查看已完成的计算机网络知识库规格（21文档/¥0.83/Homelab Context Embedding），作为「贴近用户实际运维环境的知识库」的构建模板。本模板重点记录了如何在每条知识块中嵌入用户自己的网络配置场景（如子网划分=用户内网IP段、TCP=用户代理建连过程），大幅提升知识留存率。\\n**数学公式类知识库模板：** `skill_view('knowledge-rag-ingestion', 'references/math2-knowledge-base-complete.md')` 查看已完成的数学二知识库规格  
**经验/实践型领域知识库模板：** `skill_view('knowledge-rag-ingestion', 'references/finance-knowledge-base-complete.md')` 查看已完成的A股金融知识库规格（35条/¥1.45/3路并行/用户持仓嵌入），作为「非教科书类、依赖网络信源+用户实际场景嵌入的知识库」的构建模板。本模板重点记录了：经验类知识源从BrightData搜索而非canonical教材、用户持仓直接嵌入知识块、`architecture_modules`字段在非计算机领域的语义迁移（分类框架）、以及A股特有机制（T+1/涨跌停/打板）如何在知识块中突出。（15文档/228KB/¥0.89/公式速查豁免模板），作为「公式/演绎类知识库」的构建模板。本模板关键记录了：公式速查表可豁免17字段、易错点独立成块更高效、解题方法单独存放等适用于数学类内容的差异化策略。  \\n**合并子领域知识库模板：** `skill_view('knowledge-rag-ingestion', 'references/english-knowledge-base-complete.md')` 查看已完成的英语通用应试知识库规格（24文档/356KB/¥1.10/英二+六级合并），作为「合并重叠子领域为一个统一知识库」的构建模板。本模板记录了：哪些部分合并（词汇/语法/阅读）、哪些保留独有（听力/写作）、合并后节省33%成本的具体数据，以及作文模板类知识的差异化策略（detailed_explanation≥1000字）。

## When to Use

- 用户说"帮我研究一下XXX"或"调研一下XXX"
- 用户发来PDF/文档要求整理入库
- 回答用户问题时发现某个知识点不熟悉，需要先研究再回答
- 用户有新的技术文档、课件、考研资料需要存入RAG
- 发现RAG知识库中某个领域的信息不完整或过时

**不要用于：** 简单的单次问答、不需要长期记忆的一次性任务、纯娱乐内容。

### ⛔ 什么时候不该建RAG（负向过滤器）

**不是所有领域都值得花token建RAG。** 用户对token成本敏感，主动询问"这个值不值得做"时，要诚实评估。

**❌ 不值得做的典型场景：**

1. **快速变化的内容** — 如考研政治（大纲每年变、时政每月更新）、行业新闻、产品版本迭代。RAG做进去的知识几个月就过期，不如直接看最新资料。

2. **刷题驱动的应试科目** — 如考研政治、英语作文模板。这类科目核心复习方式不是查知识库，而是大量刷选择题、背特定模板。买本精讲精练或刷题APP的效果远超RAG。

3. **已有成熟教材的内容** — 如果一本教材/精讲就能覆盖全部知识点，且用户已有纸质/电子版，RAG只是多此一举。RAG的价值在于**整合多源分散信息**，而不是复读一本已有教材。

4. **变异性低+信息密度低的内容** — 比如单纯的公式罗列、词汇列表、常识性内容。用一张速查表或单词APP比RAG更高效。

5. **短期使用场景** — 用户只问一两次就不再需要的内容。RAG的维护成本和token消耗远高于直接在对话中查一次。

**✅ 做RAG前问自己三个问题（必须全部满足）：**
- 🔲 这个知识领域是否**相对稳定**（半年内不会过时）？
- 🔲 用户是否需要**跨会话检索**（不是一次性问答）？
- 🔲 信息是否**分散在多个来源**（不是一本教材就能搞定）？

如果三个问题中有一个"否"，先跟用户说明理由，让用户做最终决定。

**实战案例（来自本用户的真实反馈）：**
- 用户问"考研政治做知识库有用吗" → 评估后建议不做（变化快+刷题驱动+有教材） → 用户同意 ✅
- 用户问"A股金融知识做RAG有用吗" → 评估后建议做（相对稳定+长期使用+多源分散） → 35条知识块入库 ✅

## 四阶段 Pipeline

### 第一阶段：Research Planning（研究规划）

**目标：** 分析领域，构建知识树与Topic Map。

1. **领域分析：** 识别核心领域范围、边界、子领域
2. **知识树构建：** 拆分为：
   - 一级主题（核心领域模块）
   - 二级主题（子模块 / 功能组件）
   - 核心概念（Key Concepts）
   - 架构模块（Architecture Components）
   - 常见问题（FAQ / Common Issues）
   - 性能瓶颈（Performance Bottlenecks）
   - 最佳实践（Best Practices）
   - 版本差异（Version Differences）
   - Failure Cases & Edge Cases
3. **优先级排序：** 从最核心/最常用的知识开始，告知用户研究计划

**输出：** `research_plan.md` — 知识树结构+优先级+预计知识块数量
  ⚠️ **文件位置规范：** `research_plan.md` 和后续的 `research_notes.md` 必须放在本次知识块的输出目录中（如 `/root/rag-data/os_knowledge_blocks/` 或 `.../cn_network_blocks/`），不要放在 `/root/rag-data/` 根目录下。根目录积累多个计划文件会造成混乱。如果输出目录尚未创建，先创建再写入。

### 第二阶段：Targeted Research（定向研究）

**目标：** 基于知识树进行定向研究，而不是全网随机搜索。

1. **来源优先级：**
   - 🥇 官方文档 / 官方GitHub仓库
   - 🥇 GitHub Issues / PR / Wiki
   - 🥇 学术论文（arXiv, Google Scholar）
   - 🥈 知名技术博客（各大厂技术团队）
   - 🥈 StackOverflow 高质量问答
   - 🥉 Reddit 讨论
   - ❌ 低质量聚合站、未经验证的博客
2. **来源可信度评分：**
   - 官方 = 5/5
   - 知名博客/论文 = 4/5
   - StackOverflow高分 = 3/5
   - 社区讨论 = 2/5
3. **多源共识机制：** 至少2个可信来源确认同一结论才写入

**输出：** `research_notes.md` — 每条的来源URL+可信度+核心发现

### 第三阶段：Knowledge Distillation（知识蒸馏）

**核心原则：AI必须"理解后重写"，而不是复制原文。**

## 17字段速查表（打印出来对照！）

构建每条知识块时，必须回来对着这张表逐一打勾，打满再提交：

| # | 字段 | 必须？ | 要求 |
|:-|------|:------:|:-----|
| 1 | title | ✅ | 精确可检索，中英文 |
| 2 | summary | ✅ | 30-80字，一句话总结 |
| 3 | core_concepts | 🔴 | 1-3句话提炼本质 |
| 4 | detailed_explanation | ✅ | 800-2000字，含代码 |
| 5 | architecture_modules | 🔴 | 存储结构+操作分类 |
| 6 | keywords | ✅ | 20+中英文 |
| 7 | best_practices | ✅ | 6+条 |
| 8 | limitations | ✅ | 4+条 |
| 9 | common_problems | ✅ | 5+个 |
| 10 | failure_cases | 🔴 | 3+个易错场景 |
| 11 | edge_cases | 🔴 | 5+个边界条件 |
| 12 | performance_bottlenecks | 🔴 | 3+个 |
| 13 | related_concepts | ✅ | 5+个 |
| 14 | source_url | ✅ | 真实来源（≥2个） |
| 15 | confidence | ✅ | 1-5 |
| 16 | applicable_scenarios | 🔴 | 5+个适用场景 |
| 17 | embedding_text | ✅ | 300-500字高密度 |

**🔴 = 最容易遗漏的字段，写完后必须检查这5个！**

#### 每条知识块的结构化字段（完整版·必须全部包含）

```python
{
  "title": "Redis 大 Key 性能问题及解决方案",        # 精确、可检索的标题
  "summary": "一句话总结本条知识",                   # 30-80字
  "core_concepts": "核心思想提炼（1-3句话）",        # 🔴 必须！提炼本质
  "detailed_explanation": "详细说明（800-2000字）",  # AI理解后重写，含代码示例
  "architecture_modules": {                         # 🔴 必须！存储结构/操作分类
    "存储结构": "顺序/链式",
    "操作类别": "插入类/删除类"
  },
  "keywords": ["redis", "big key", "性能"],          # 中英文20+关键词
  "best_practices": ["定期scan扫描大key"],            # 6+条实战建议
  "limitations": ["拆分后事务一致性需额外处理"],      # 4+条固有缺陷
  "common_problems": ["del大key导致阻塞"],            # 5+个常见问题
  "failure_cases": [                                  # 🔴 必须！易错/失败场景
    "顺序表满时继续入栈导致数据越界",
    "快排对有序数组退化为O(n²)"
  ],
  "edge_cases": [                                     # 🔴 必须！边界条件
    "空栈出栈导致段错误（下溢）",
    "所有元素相等时快排最坏O(n²)"
  ],
  "performance_bottlenecks": [                        # 🔴 必须！性能瓶颈
    "Floyd算法O(n³)不适合大图",
    "链栈malloc/free开销大"
  ],
  "related_concepts": ["Redis内存管理", "键过期策略"],
  "source_url": "https://...",                        # 真实来源URL
  "confidence": 4,                                    # 1-5可信度
  "applicable_scenarios": [                           # 🔴 必须！适用场景
    "实时排行榜",
    "分布式锁"
  ],
  "embedding_text": "用于向量检索的高密度文本（300-500字）"
}
```

**🔴 标记的字段是用户特别在意、初次构建时最容易遗漏的。** 遗漏这些字段会显著降低知识库的深度和召回质量。每次构建知识库时必须逐一核对此模版，确保没有遗漏。

#### Chunk Methodology（切块策略）

**按知识语义切块，而不是固定字数。**

- ✅ 每个Chunk聚焦**单一知识主题**，如"Redis大Key性能问题"
- ✅ 每个Chunk包含：完整问题描述 + 解决方案 + 限制条件 + 技术术语 + 适用场景
- ❌ 禁止：同一Chunk混杂多个主题
- ❌ 禁止：直接存储原始网页、大段博客、低质量长文本

#### Embedding Text 优化

每条知识生成专用 `embedding_text`：
- 200-500字，高密度
- 包含该知识所有核心术语和同义词
- 用自然语言描述，而非keyword堆砌
- 覆盖用户可能使用的各种问法

**示例：**
> "Redis big key（大键）是指包含大量数据（如大List/Hash/Set/String超过10MB）的键。它们会导致del命令阻塞Redis进程、造成主从同步延迟、占用大量内存。解决方案包括：用scan扫描大key、手动拆分value、使用unlink异步删除、设置合理淘汰策略。相关命令：redis-cli --big-keys、memory usage、debug object。"

### 第四阶段：Memory Optimization（记忆优化）

**目标：** 入库前的最终优化。

1. **语义去重：** 检查库中是否有内容重复或高度相似的知识块，合并或覆盖
2. **版本合并：** 同一主题的新旧版本知识自动合并，保留版本差异
3. **置信度更新：** 新知识置信度高于旧知识时，用新知识覆盖
4. **关键词强化：** 补充搜索时可能用到的同义词、缩写、别名
5. **上下文压缩：** 去除冗余表达，保持每条800字以内
6. **入库：** 写入SimpleRAG数据库（`/root/rag-data/db/`）

**验证：** 执行一次搜索测试，确认召回效果

## Token Cost & Efficiency（用户关注的成本透明度）

用户注重 token 消耗效率。完成知识入库后，**必须**主动汇报本次任务的 token 估算成本，让用户知晓花费。

### 估算方法

**主要成本来源（按损耗排序）：**
1. **大脚本代码**（批量生成知识块）：每次 `execute_code` 中的 Python 代码 + 文本数据会全部作为输入 token 消耗。24条知识块约需要 2次 execute_code（~7.4K tokens in）。
2. **对话上下文**：系统提示词（~10K/轮） + 上下文累积。约10轮对话。
3. **输出 token**：每条知识块本身是 AI 输出，但通过 write_file 写入文件不产生输出 token；仓库的回答和状态汇报产生少量输出。

**估算公式（供汇报用）：**
```
输入 ≈ 大脚本嵌入(~7K) + 系统提示(10K×轮数) + 上下文累积(平均5K×轮数)
输出 ≈ 1-2K/轮 × 轮数
```

**DeepSeek V4 Flash 参考价格（中国区 API）：**

系统提示词每轮重复发送，大部分属于**缓存命中**，按命中价计费。新内容（代码、搜索结果、首次提问）属于**缓存未命中**。

| 类型 | 价格 |
|------|:----:|
| 输入缓存命中 | ¥0.02/百万tokens |
| 输入缓存未命中 | ¥1/百万tokens |
| 输出 | ¥2/百万tokens |

**典型比例假设：**
- 缓存命中（系统提示词每轮重复 ~10K/轮）：约 ~40% 输入
- 缓存未命中（新内容）：约 ~60% 输入

**汇报模板（最终汇报）：**

```markdown
💰 Token 账单（近似）：
- 总输入：~XXXK（缓存命中 ~XX%，缓存未命中 ~XX%）
- 总输出：~XXK
- 合计：~XXXK
- 预估成本：¥X.XX
```

### 效率原则
- 10条以内的知识块，一次执行即可
- 超过10条分两批（先用~5条验证格式，再批量生成剩余）
- PM25搜索验证时，用1-2个不同角度的关键词即可，不需要全覆盖验证

## 知识图谱（Knowledge Graph）

每当研究一个新领域，自动构建领域知识图谱：

```
Redis
├── 数据结构
│   ├── String（set/get）
│   ├── List（lpush/lpop）
│   ├── Hash（hset/hget）
│   └── 大Key问题 ← 知识块A
├── 持久化
│   ├── RDB
│   └── AOF
├── 集群
│   ├── 分片
│   └── 主从同步
└── 性能
    └── 大Key性能影响 ← 知识块A
```

每个Topic关联对应的Knowledge Block ID，后续可通过知识图谱导航查询。

## Self-Evolving RAG（自进化机制）

当用户提问时：

1. 搜索RAG知识库
2. 如果找到相关内容 → 结合回答
3. 如果**未找到**或**信息不足** → 自动触发：
   - 识别知识缺口
   - 生成研究计划
   - 执行Pipeline（阶段1-4）
   - 入库 + 告知用户"已补充新知识"

## Practical Execution Flow

### 场景A：用户要求研究某个领域

⚠️ **用户经常质疑\"自己知道的内容建RAG还有用吗\"** → 参考 Pitfall #17 的解释话术。这非常关键——不做这个解释，用户会认为知识库毫无价值。

```
1. 阶段1：输出研究计划给用户确认
   → \"我计划从以下维度研究Redis：数据结构、持久化、集群、性能优化...\"
2. 阶段2：执行研究
- **优先使用 BrightData**（针对中文内容/考研/学术搜索效果最佳）  
- 如果 BrightData 搜索也无效，考虑直接用 canonical（标准教材/官方文档）知识蒸馏  
- 避免使用 openwebsearch（Bing引擎）搜索中文垂直内容（如\"408考研\"），结果偏题严重  
- 搜索目标：获取至少2个可信来源的同主题内容用于交叉验证，而非完全依赖搜索结果  
- **重要区分（考研/认证考试类内容）：** 对于高度标准化的教材知识（408考研、CET、CCNA等），BrightData的作用是**获取source_url用于交叉验证**，而非发现新知识。内容主体直接来自canonical教材（如王道考研、汤小丹教材），BrightData搜到的博客/专栏主要提供表述多样性和URL引用。这个模式与纯技术领域（如新框架、新工具）不同——后者BrightData是主要的知识来源。参见 `references/os-knowledge-base-complete.md` 了解OS案例。
3. 阶段3：蒸馏知识，每块结构化
   - **必须包含全部17个字段**——逐个字段检查再提交，不要遗漏
   - 超过10条知识块时，用 delegate_task 并行分发到多个子Agent
     （设置 max_concurrent_children=3，每个子Agent负责一个子领域）
   - 子Agent输出 write_file 到共享目录，父Agent统一入库
   - **🏠 Homelab Context Embedding（重要技巧）：** 当知识领域与用户日常运维/排障高度重合时（如网络/路由/代理/DNS），在子Agent prompt中明确要求每条知识块嵌入用户真实环境场景。例如计算机网络知识库中，子层IP地址=用户内网192.0.2.0/24、TCP建连=用户Clash代理过程、DNS=用户Clash DNS分流配置。**效果验证：** 用户看到\"这个我遇到过\"反应 → 知识留存率远高于纯理论。参考 `references/cn-network-knowledge-base-complete.md`。
   - **🎯 合并相关子领域（新技巧）：** 当两个目标领域知识点高度重叠时（如英二和六级、或思科CCNA和华为HCIA），**建议合并为一个统一知识库**而非分开建设。优点：①避免知识重复入库（词汇/语法/阅读方法是完全共享的）；②用户跨考试检索时能一次命中；③总成本低于两个独立知识库之和。做法：研究计划中直接按\"共享部分 + 各自特有部分\"结构规划，子Agent prompt中标记`target_exam`字段区分。
   - **🔗 跨模块交叉引用（新技巧）：** 对于关联紧密的知识模块（如英语词汇↔语法），在每一条数据中植入交叉引用字段。示例：单词条目中加 `见:非谓语(过去分词作定语)`，该字段被BM25直接索引，用户搜词时同时匹配到语法知识块。实现方式：在子Agent prompt中提供可用关联模块名录（如`eng_grammar_*`、`eng_phrasal_verbs`），要求每条知识块至少关联1-2个其他模块。该模式适用于任何存在层层递进关系的领域（如计算机组成原理→汇编指令、数学公式→解题方法）。
   - **⚠️ 子Agent时间超时（pitfall #23）：** 生成大量结构相似的批量条目（如英语词汇表、公式速查表）时，子Agent的600秒超时限制会频繁触发。子Agent生成→write_file→继续生成的循环中，每条API调用和文件写入都会累积时间。**解决方案：** ①单次任务覆盖不超过500-600条；②优先让子Agent直接write_file一整批而非逐条写入；③如果超时则检查已写入部分（超时前的写入可能已完成），分小批继续；④对超大规模的词汇/列表类任务，考虑直接通过execute_code用Python脚本生成模板化内容，避免完全依赖AI逐项生成。

**⚠️ 子Agent超时导致partial write未检测（pitfall #24）：** 在Phase 3用delegate_task并行生成知识块时，如果子Agent超时（600s），它可能已经完成了部分文件的写入退出后才超时报错。**永远不要立即重试整个批次——先检查输出目录中已存在的文件数。** 在实践中，一个写14个文件的子Agent超时但已写入10个到磁盘；重新delegate时只补剩下的4个即可。在子Agent超时后，先`ls`目标目录统计已写文件数，只delegate缺失的部分。如果第二个子Agent再次超时，可能第一批的写入其实已经100%完成了（超时发生在前一次API调用的等待阶段，而非写入阶段）。直接检查文件完整性即可。

**⚠️ RAG→Obsidian导出时子Agent过载（pitfall #25）：** 用delegate_task并行执行RAG→Obsidian转换时，每个子Agent需要读取大量知识块文件（17字段解析）+ 逐条转换格式。如果单个子Agent负责的学科文件数超过30个（如OS+英语+金融=~91个），虽然任务数不在同一子Agent内，但读取阶段的累积输入token可能很大。**建议分批粒度：** 每次delegate不超过3个子Agent，每个子Agent分配的txt文件不超过50个。英语词汇类（eng_vocab_*.txt体积大，每条上千行）应单独拆出一个子Agent。

4. 阶段4：优化+入库
   - 如果已有旧版知识，先清空RAG DB（删除 documents.json + chunks.json）
     再重启gateway让SimpleRAG加载空白DB，然后重新入库
   - 如果不清理，旧版和新版会混在一起，降低召回质量
5. **汇报结果**：
   - 告知用户已入库数量、覆盖领域
   - **附 Token 成本估算**（参考 Token Cost & Efficiency 章节的汇报模板）
   - 可提供**知识库可视化地图**（如 excalidraw 思维导图），满足用户"想看知识库"的需求
   - 如果用户问"能不能把我的RAG转成Obsidian"或"想在Obsidian里看"（俗称"从RAG吐出来"）:
     1. 加载 `skill_view('knowledge-rag-ingestion', 'references/rag-to-obsidian-export.md')` 查看完整方案和执行记录（截至2026-05-18已产出187篇/7学科/3.1MB）
     2. 核心思路：用3路delegate_task并行，每路负责2-3个学科
     3. 转换模板：解析17字段.txt -> YAML frontmatter + 正文（含emoji callout高亮）
     4. 按学科分文件夹，每学科一个MOC索引文件 + 跨学科总关联图
     5. 特殊文件豁免：词汇类/作文模板类/公式速查类保留原格式
     6. 英语词汇文件体积大，应单独分配一个子Agent

**单学科导出模式（新增）：** 当只有1个学科/领域需要导出（如文明六27条），不需要delegate_task并行。核心流程：
1. 写一个Python脚本，遍历该学科目录下所有.txt文件
2. parse函数须同时处理3种格式（见pitfall #24），切勿假设格式统一
3. 将标题按 `|` 或 `（` 分割，只保留中文主标题作为文件名，排除英文副标题避免文件名过长
4. 输出到 `obsidian-vault/学科名/`，每篇一个.md文件
5. 生成MOC索引文件（`XX索引.md`），按类别分组（胜利条件/城市建设/系统机制等）
6. 用 `tar czf` 打包整个目录，通过 `send_message` 微信发送（`MEDIA:/path/to/package.tar.gz`）
7. 索引文件中的 `[[wikilink]]` 必须对应实际文件名（不含.md后缀）
```

### 场景B：用户发来文档要求入库

```
1. 读取文档（PDF/TXT/MD）
2. 如果格式不支持 → 转成TXT
3. 拆分成语义chunk
4. 每个chunk：生成结构化字段
5. 优化 + 入库
6. 验证搜索效果
```

### 场景C：回答中发现知识缺口

```
1. 记录缺口主题
2. 回答后告知用户："关于XX我当前知识库没有覆盖，正在研究中..."
3. 异步执行Pipeline
4. 完成后通知用户
```

## RAG 工具使用

知识入库通过SimpleRAG MCP工具（配置在 `~/.hermes/config.yaml` 的 `mcp_servers.simple-rag`）：

- `rag_ingest(filepath)` — 将文件直接导入（TXT/MD最佳，PDF中文内容建议先转TXT）
- `rag_search(query, top_k=3)` — 验证召回效果
- `rag_status()` / `rag_list()` — 查看状态

**MCP协议注意：** 自定义MCP服务器必须使用标准 `tools/list` 和 `tools/call` 方法名（而非 `list_tools`/`call_tool`），且遵循 `{"jsonrpc":"2.0","id":...,"method":"tools/list","params":{}}` 格式。首次启动gateway可能因超时失败（CancelledError），需增加 `timeout` 到120秒或在config中设置 `connect_timeout`。配置变更后重启gateway生效。

**🚨 mcp-compressor兼容性（踩坑经验）：** 如果自定义MCP服务器通过 `mcp-compressor` 包装运行，initialize 响应中**必须**包含 `serverInfo` 字段，否则FastMCP会报 `ValidationError: Field required` 拒绝连接。原因是mcp-compressor底层使用FastMCP库，它严格校验MCP协议的InitializeResult格式。正确的initialize响应示例：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {"tools": {}},
    "serverInfo": {"name": "simple-rag", "version": "1.0.0"}
  }
}
```
注意：`protocolVersion` 必须用 `"2024-11-05"`（当前标准），不要用旧的 `"0.1.0"`。

**SimpleRAG后端路径：** `/root/rag-data/`，数据库在 `/root/rag-data/db/`，MCP服务脚本在 `/root/rag-data/rag_mcp_server.py`，核心RAG实现在 `/root/rag-data/simple_rag.py`。

## Visual Output Preference: HTML → Screenshot (Not Python Pillow)

When producing visual/architectural diagrams for plans (知识树结构图、方案对比图、推荐排行图):

**User preference (from session 2026-05-18):** The user asked "html做不了吗" when the agent tried Python Pillow-generated PNG. The correct workflow is:
1. Write a clean self-contained HTML file with inline CSS
2. Use Chrome headless for screenshot: `google-chrome --headless --disable-gpu --no-sandbox --screenshot=output.png --window-size=W,H file:///path/to/file.html 2>&1 | grep "written"`
3. Send the PNG via `MEDIA:/path/to/output.png`

**Avoid:** `PIL/Pillow` for visual diagrams — it requires font installation, has poor Chinese text rendering without Noto/Source Han fonts installed, and the user explicitly asked "can't you do HTML instead".

**Chrome headless tips for this environment:**
- Always use `--no-sandbox` flag (running as root in LXC)
- Set `--window-size=820,H` where H ≈ content height + 50px padding
- Fonts: if `NotoSansCJKsc-*.otf` exists in `/usr/share/fonts/noto-cjk/`, Chrome auto-picks them via `font-family: 'Noto Sans CJK SC', sans-serif'
- Template: `templates/html-plan-screenshot.html` (use as base for any plan/architecture comparison screenshot)

---

## 📁 Obsidian 导出（RAG→Obsidian conversion）

当用户要求将RAG知识库转为Obsidian笔记时：

1. **参考模板：** `skill_view('knowledge-rag-ingestion', 'references/rag-to-obsidian-export.md')`
2. **核心流程：** 解析17字段.txt → YAML frontmatter + Markdown body → 按学科分文件夹输出
3. **格式兼容性注意：** 同一知识块目录下的 .txt 文件可能使用 **3种不同格式**，需一起处理：
   - **格式A（17-Field）：** `Field: xxx` / `Value: xxx` 逐行（第一批知识块）
   - **格式B（YAML-like）：** `title: xxx` / `summary: xxx` / `detailed_explanation:` 等 key-value 直写（第二批知识块）
   - **格式C（Numbered）：** `--- N. fieldname ---` 或 `N. fieldname` 编号格式（第三批知识块）
4. **必须处理所有3种格式**，不能假设目录内格式统一
5. **输出规范：** 每学科一个文件夹 + 一篇MOC索引（`XX攻略索引.md`）+ 双向链接 + emoji callout
6. **打包发送：** 输出后 `tar czf` 打包并通过send_message微信发送
7. **特殊条目豁免：** 词汇类/公式速查类保留紧凑列表格式，仅加YAML frontmatter

## ⚠️ 已入库但RAG DB被清空后的恢复策略（重要）

SimpleRAG的向量数据库（SQLite+JSON文件）可能因多种原因被意外清空或重建（gateway重启、磁盘清理、旧版重装等）。**症状：** `rag_list` 显示知识文件存在（文件系统上 `blk_agent*.txt`、`math2_*.txt`、`ds_*.txt` 等都在），但 `rag_search` 搜不到任何内容或只搜到部分内容（如只搜到金融的 `blk_agent*` 但搜不到 `math2_*`、`ds_*`、`eng_*` 等）。

**用户在此场景非常敏感**——上一会话他问\"我们的RAG知识库不是建了好几个领域的吗\"，我因只查到部分内容就断言\"还没正经建起来\"，被他立即纠正。他对自己花token建的知识记得清清楚楚。

**恢复流程：**
1. 先 `rag_list` 检查当前库中到底有哪些文件
2. 再看文件系统目录 `/root/rag-data/` 下有哪些知识块目录：
   - `finance_knowledge_blocks/` — 金融35条
   - `co_knowledge_blocks/` — 计算机组成原理~30条
   - `math2_blocks/` — 数学二15条
   - `os_knowledge_blocks/` — 操作系统22条
   - `cn_network_blocks/` — 计算机网络21条
   - `knowledge_blocks/` — 数据结构24条
   - `english_blocks/` — 英语34条（含词汇、语法、阅读、写作、翻译）
3. 确定缺失的科目后，直接用 `rag_ingest(filepath)` 逐文件或逐目录重新入库
4. 入库后用 `rag_search` 测试不同关键词验证召回

**注意：** 不需要重新生成知识块文件，文件一直都在！只需要重新 `rag_ingest` 即可。如果所有文件都已入库但搜不到某些科目，也是同样的恢复流程。

**变体场景 —— 部分科目从未入库（人话：不是丢了，是压根没塞进去）：** 此场景与RAG DB被清空不同——某个API key额度用尽、task超时、建库流程被中断等原因，导致某些科目文件已经存在但从未被 `rag_ingest` 过。症状：`rag_list` 只看到部分文件（如 `blk_agent*`、`co_*`），`rag_search` 搜不到其他科目内容。**用户在此场景反应激烈（真实案例）：** 他说"你之前明明建了408和数二还有英语，怎么又说没了"，因为他亲眼看着文件和目录被创建，但Agent只查到RAG DB里没有就断言"没建"——这是严重的信任损害。**正确的判断流程：** ①先 `rag_list` 查RAG DB；②再检查文件系统 `/root/rag-data/` 下各知识块目录是否存在（`finance_knowledge_blocks/`, `co_knowledge_blocks/`, `math2_blocks/`, `os_knowledge_blocks/`, `cn_network_blocks/`, `knowledge_blocks/`, `english_blocks/`）；③如果文件在但RAG搜不到 → 直接重新入库，不要下结论说"没建"。

## Common Pitfalls

1. **存储原始网页/大段原文** → RAG召回质量差，禁止。必须AI理解后重写。
2. **知识块混杂多个主题** → 召回时语义模糊。必须单一主题。
3. **embedding_text太短** → 向量召回容易miss。至少200字，覆盖核心术语。
4. **不做去重** → 同一知识重复存储，浪费token。入库前必须检查。
5. **忽略中文关键词** → 用户用中文提问时搜不到。必须同时包含中英文关键词。
6. **一次存入太多** → 用户等待太久。超过10条知识块时分批告知进度。
7. **来源单一** → 知识可能不准确。至少2个可信来源。
8. **不验证召回** → 入库后务必用rag_search测试一下能否搜到。
9. **PDF中文解析失败** → 某些PDF解析器(muPDF)对中文PDF支持差。先用PyPDF2提取文本存为TXT再喂。
10. **HuggingFace模型下载被墙** → 国内无法下载embedding模型（即使通过代理/hf-mirror）。
    解决方案：使用纯本地BM25关键词搜索替代向量搜索（如本项目的SimpleRAG实现，零模型依赖）。
11. **Node.js版本不够** → 某些RAG MCP服务器（如mcp-local-rag）需要Node.js ≥22.12。
    升级命令：`curl -sL https://nodejs.org/dist/v22.13.0/node-v22.13.0-linux-x64.tar.xz | tar xJ -C /usr/local/ --strip-components=1 --wildcards '*/bin' '*/include' '*/lib' '*/share'`
12. **自定义MCP服务器连接超时** → gateway对MCP服务器的初始连接有超时限制。
    `CancelledError` 表示服务启动太慢被取消。使用标准MCP协议格式（`tools/list`/`tools/call`），增加config中的`timeout: 120`。

13. **mcp-compressor包装自定义服务器时缺少serverInfo** → 自定义MCP服务器被mcp-compressor包装后，FastMCP/Pydantic会校验initialize响应中的 `serverInfo` 字段。缺失则报 `ValidationError: Field required`。必须在initialize响应中返回 `{"name":"...","version":"..."}`。

14. **BM25关键词搜索对特殊字符不敏感** → SimpleRAG使用BM25关键词搜索（非向量搜索）。特殊字符如 `B树`、`C++`、`.NET` 等可能匹配不到短查询词。解决方案：embedding_text中**展开拼写**（如"B树"→"B树B-tree m阶多路平衡查找树"），并包含中英文对照关键词。同时向rag_search传入多个同义关键词以提高召回率。

15. **搜索工具选择错误** → openwebsearch（Bing引擎）搜索中文垂直内容（如"408考研 数据结构"）结果极差——Bing会优先返回研招网等泛官方页面，完全屏蔽真正的内容页面（CSDN、知乎、博客园）。**正确做法：发现一次搜索无效后立即切换 BrightData**，BrightData的自定义搜索引擎对中文技术内容效果好得多。如果BrightData也失败（如被墙的站点），才考虑用canonical知识直接蒸馏。

16. **"自知识RAG"被用户质疑价值** → 当用户问"你自己已经知道的内容建RAG还有用吗？"，需要清晰解释为什么有用：

    - **持久性**：RAG跨会话保留，模型知识会话结束后就没了
    - **一致性**：同一问题每次得到相同答案，而非模型随机生成
    - **精确性**：结构化字段（ASL公式、代码示例、测试数据）比模型临时生成更可靠
    - **可编辑可纠错**：发现错误改一条txt永久修正，无法改模型训练数据
    - **可叠加**：408四科可以逐步填满，跨领域检索能力远超单一模型
    - **模型无关**：换不同LLM后知识库依然可用

    解释时用类比：这不是"抄自己的笔记"，而是"把自己的正确答案录成永久音频，每次播放都一样清晰"。

19. **DCache会话断开后MCP工具不可用** → Gateway重启后，MCP工具（如rag_ingest）可能因会话断开而超时。此时需要：`systemctl restart hermes-gateway`，等待8-15秒让所有MCP服务完成重连，再执行工具调用。如果第一次调用超时，重试一次通常成功。

20. **大词表生成时子Agent超时** → 生成结构化词汇表（如英语核心词1750条）时，子Agent的600s超时限制容易被突破。解决方案：每批控制在**500条以内**，或让子Agent分段生成后`cat`合并。若超过500条，拆分为多个子Agent并行，各写一个临时文件后合并。

21. **旧版DB未清理就重新入库** → RAG DB中的旧版文件会和新版文件混在一起，降低搜索质量。替换旧版知识时必须先清空：`rm -f /root/rag-data/db/documents.json /root/rag-data/db/chunks.json && systemctl restart hermes-gateway`，然后等待gateway完全启动后再入库。

19. **子Agent使用自创字段名而非标准模板** → 子Agent的prompt中只说"用17字段模板"不够，子Agent会自行发明字段名（如`key_points`/`formulas`/`exam_tips`而非标准的`core_concepts`/`keywords`/`best_practices`）。虽然BM25全文搜索不受字段名影响，但这破坏了跨模块一致性，且未来向量化搜索时会丢失字段对齐。**解决方案：** 子Agent prompt中必须**逐行粘贴17个字段名及其格式**（从本SKILL的17字段速查表复制），而不是只写"按17字段模板"。对特殊类型知识块（如公式速查表）可豁免模板要求，但需在prompt中明确说明。同时使用terminal做字段名grep验证：`grep -c '^core_concepts:'块/*.txt; grep -c '^failure_cases:'块/*.txt; ...`。

20. **子Agent生成批量数据超时（Subagent timeout on batch generation）** → 生成大量结构相似的条目（英语词汇表500+条、公式表300+条等）时，子Agent的600秒超时限制会频繁触发。原因是：生成→write_file→继续生成的循环中每条调用和写入累积时间。**解决方案：** ①单任务不超过500-600条；②优先让子Agent一次性write_file整批而非逐条写入；③超时后检查已写入部分，剩余内容分小批继续；④超大规模列表类任务考虑用execute_code生成结构化模板，减少AI逐项生成的token和时间消耗。

22. **AI认为自己"懂这个领域"就跳过研究阶段** → AI在用户已经提供了详细知识清单（如"请加入A股技术分析/基本面/行为金融学知识"）时，容易产生"这些我都知道，直接写就行"的错觉，从而跳过整个Phase 2（Targeted Research），不搜索多源资料，不输出research_notes.md，直接凭自己的知识写知识块。**用户对此非常敏感**——他明确批评了"你没按skill流程来"。**判断标准：** ①如果用户给了明确的知识主题（如"帮我做金融知识库"），这恰恰是需要研究的信号——需要去查资料获取source_url和多源验证；②仅当知识块属于canonical教材知识（如408考研内容，来自王道/汤小丹教材的标准概念），且用户已经认可canonical优先策略时，才能跳过研究。**正确做法：** 即使用户给的主题你很熟悉，也必须：输出research_plan.md→用BrightData搜索→多源验证→research_notes.md→子Agent并行生成→验证召回。

23. **Agent自身崩溃/重启导致Phase 3中断（恢复模式）** → Agent可能在Phase 3执行过程中意外崩溃（上下文超限、gateway重启、系统OOM等）。重启后的会话没有Phase 3中已完成工作的记忆。**灾难性错误：** 不检查文件系统就直接从头开始重新生成——浪费token且让用户困惑"你不是做完了吗"。**正确做法：** ①`ls <输出目录>/*.txt | wc -l` 统计已有文件数；②读research_notes.md确认计划总条数；③计算差额，只补缺少的部分；④如果已有文件数 >= 计划数，直接跳到Phase 4入库验证。**真实案例：** 文明六RAG构建时，24条已生成完成但Agent崩溃→重启后检查目录发现24个文件→只补3条缺的→入库27条→验证通过。

**旁路：Agent崩溃后rag_list显示空库（pitfall #27）：** Agent在Phase 3生成完所有.txt文件后可能在执行rag_ingest前崩溃。症状：文件在磁盘上，但rag_list返回空。**恢复流程：** ①ls输出目录确认文件存在；②rag_list查DB确认空；③直接rag_ingest所有文件补入库，无需重新生成文件。

**⚠️ Phase 3知识块文件存在3种不同格式（pitfall #24）：** 不同子Agent或不同批次的生成脚本可能在Phase 3输出不同格式的知识块文件。真实案例（文明六）：27条文件中用了(A) 17-field标准格式 `Field: xxx / Value: xxx`；(B) 编号格式 `--- N. fieldname ---` + 下文内容；(C) YAML-like格式 `key: value`（冒号+空格分割）。**症状：** RAG→Obsidian导出后部分文件只有100-200字节（只有标题和frontmatter，正文丢失）。**正确做法：** 导出脚本的parse函数必须支持3种格式自动检测——检测首行特征（`Field:`、`--- N.`、或裸`key:value`），分配对应解析分支。推荐写一个 `parse_knowledge_block(text)` 统一函数处理3路分支。

25. **RAG→Obsidian导出文件名过长（格式整洁）**

⚠️ Pitfall #24已经在Common Pitfalls列表中标出。对应的解决方案：在Obsidian导出脚本中实现统一解析函数，检测知识块文件的第一行特征，自动选择解析分支。

26. **数学/公式类知识块使用错误字段模式**

## ⛔ 预检清单（每次加载此Skill时逐条打勾后再动手！）

**读到这里先停一下！** 下面的checklist不打勾，你的执行结果一定会有遗漏。**每完成一个步骤，回来打个勾。**

### 启动前（必须）\n- [ ] 已读"AI容易犯的错"7条
- [ ] 已确认不能跳阶段、不能跳字段

### 阶段1：Research Planning
- [ ] 已输出 `research_plan.md`（知识树+优先级+预计条数）
- [ ] 已告知用户研究计划

### 阶段2：Targeted Research
- [ ] 优先使用 BrightData 搜索（而不是 openwebsearch）
- [ ] 每条知识块 ≥2个可信来源（source_url填满）
- [ ] 已输出 `research_notes.md`（来源URL+可信度+核心发现）

### 阶段3：Knowledge Distillation
- [ ] 每条知识块已包含**全部17个字段**（对照速查表逐条打勾）
- [ ] **5个🔴字段已全部确认**：core_concepts / architecture_modules / failure_cases / edge_cases / performance_bottlenecks / applicable_scenarios
- [ ] 纯语义chunk，无混杂主题
- [ ] embedding_text 300-500字
- [ ] 含代码示例

### 阶段4：Memory Optimization
- [ ] 已清理旧版DB（rm + systemctl restart，如有旧版）
- [ ] 已用 rag_search（3个不同角度关键词）验证召回
- [ ] 已构建知识图谱
- [ ] 已告知用户：入库数量 + 覆盖领域 + Token账单
