# 文明六攻略知识库 — 构建总结

## 基本信息

| 项目 | 数据 |
|:----|:-----|
| 知识领域 | 文明六游戏攻略（非技术/学术类） |
| 知识块数量 | 27条 |
| 总字数 | ~170KB |
| 输出目录 | `/root/rag-data/civ6_knowledge_blocks/` |
| Obsidian输出 | `/root/rag-data/obsidian-vault/文明六攻略/`（27篇 + 索引，288KB） |
| 构建日期 | 2026-05-26 |
| 子Agent并行 | 2路（第一批12条 + 第二批12条），第三批因Agent崩溃中断 |
| 崩溃恢复 | 重启后检查目录发现24条已存 → 只补3条 → 入库27条 |

## 领域特性标记

**游戏攻略类知识库与考研/技术类知识库的核心区别：**
1. **来源不同** — 攻略信息多来自Steelseries、知乎、B站、CivFanatics社区而非canonical教材
2. **字段豁免** — `architecture_modules`、`performance_bottlenecks`、`edge_cases` 等字段在游戏攻略中语义不通，应替换为 `game_mechanics`、`power_spikes`、`matchup_tips` 等游戏相关字段
3. **时效性** — 游戏版本更新（如文明6领袖季票）可能使部分知识过时，需在research_notes中标注版本
4. **用户需求** — 用户要的是"和鸡哥双排怎么赢"的实战指导，不是概念释义

## 三种知识块文件格式（踩坑记录）

Phase 3生成的27条.txt文件实际存在3种不同格式，原因是不同子Agent使用了不同的模板：

**格式A：17-field标准格式（civ6_001-008, 025-027）**
```
=== 17-Field Knowledge Block ===
Field: title
Value: 五大胜利条件总览 | Five Victory Conditions Overview
Field: summary
Value: ...
```
→ 用 `Field: xxx / Value: xxx` 模式

**格式B：编号式（civ6_009-012）**
```
=== 文明6知识块 第9条：工业区规划与6格辐射 ===

--- 1. title ---
工业区规划与6格辐射
--- 2. summary ---
...
```
→ 用 `--- N. fieldname ---` 编号模式

**格式C：YAML-like key:value式（civ6_013-024）**
```
=== Civilization VI Knowledge Block #013 ===

title: S级文明详解 — S-Tier Civilization Strategies
summary: ...
core_concepts:
- ...
```
→ 用 `key: value` 裸冒号分割模式

**解析策略：** Obsidian导出脚本中的 `parse_block()` 必须检测首行特征自动选择解析分支。

## 导出文件名策略

从 `title` 字段提取中文主标题（`|`或`（`前的内容），排除英文副标题。例如：
- `title: 五大胜利条件总览 | Five Victory Conditions Overview` → 文件名: `五大胜利条件总览.md`
- `title: S级文明详解 — S-Tier Civilization Strategies...` → 文件名: `S级文明详解.md`

英文副标题导致文件名过长（>50字符），只保留中文主标题部分。
