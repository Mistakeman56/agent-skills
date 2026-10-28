---
name: deferred-task-tracker
description: Track deferred, long-term, or 'can't do right now' tasks for the user in a persistent wishlist file. The user explicitly asked for this system so they never have to re-request unfinished business.
license: Proprietary. LICENSE.txt has complete terms
platforms: [linux]
---

# Deferred Task Tracker (待办事项追踪)

Track user tasks that can't be done immediately — future purchases, installations, errands, or anything the user says "记上" (note it down) or "放待办" (add to wishlist).

## When to Use

Trigger on these user signals:
- "记上" / "记住了" / "加上" (save it)
- "放待办事项里" / "加待办" (add to wishlist)
- "以后做" / "回头再说" / "下次搞" (defer to later)
- "我还有个什么事" / "我有什么没做" (what's pending)
- "待办清单" / "我的待办" (show wishlist)
- "XX做完了" / "搞定了" / "完成了" (mark complete)
- "把XXX划掉" / "删除" (remove from list)

## File Structure

The wishlist lives at `~/.hermes/wishlist.md` — a single markdown file with checkboxes.

**Format:**
```markdown
# 🎯 {用户}的待办清单

> {一句话说明}

---

## 🔴 高优先级

- [ ] **任务标题** — 简短说明 + 何时做
- [ ] **任务标题** — 简短说明 + 何时做

## 🟡 中优先级

- [ ] **任务标题** — 简短说明 + 何时做

## 🟢 低优先级

- [ ] **任务标题** — 简短说明 + 何时做

---

> **最后更新：** 2026-05-16
> **怎么查：** 直接说"我的待办清单"或"我还有什么没做的"
```

## Operations

### Create / Add Entry

```markdown
# Find the right priority section, insert new item
# Use this format:
- [ ] **任务名** — 简短说明 + 何时/什么条件下做
```

### Mark Complete

Change `- [ ]` to `- [x]` (keep for history) or delete the line entirely.

### List / Show

Read the file and present the checkbox lists to the user. Group by priority.

### Update with New Info

If the user clarifies details about an existing task, edit just that line without affecting others.

## Memory Integration

Save a **compact reference** in persistent memory so you can find it in future sessions:

```
assistant的待办清单存 ~/.hermes/wishlist.md（买ChatGPT礼品卡、装VoiceBox、开香港卡买小米港股等）。问就说"我的待办清单"直接看。
```

Keep it under 120 chars. The detail lives in the file, not in memory.

## Pitfalls

- **Don't duplicate tasks:** Before adding, check if the task is already in the list (use `read_file` or `grep`). The user explicitly hates repeating themselves.
- **Don't over-prioritize everything:** Keep only 3-5 items in 🔴. Lower-priority items go to 🟡 or 🟢. Ask the user if unsure about priority.
- **Don't track session-internal tasks:** The wishlist is for real-world tasks the user needs to do (buy, install, visit, configure). Don't add meta-tasks like "回头再研究这个API" unless the user explicitly asks.
- **Remove completed items promptly:** When user says "X做完了", update the file immediately in the same turn.
- **Don't make the list read-only:** The user may want you to reorganize priorities, change descriptions, or delete items. Always comply without argument.
- **Keep descriptions actionable:** Each entry should answer "what" and "when/condition" — not "why" (that's in the session history).

## Store Full Plans, Not Just Titles

**User correction (2026-05-16):** *"你不仅要把什么事存进去，还要把我们讨论的方案都完整存进去"*

The user explicitly requires that each task entry contain the **COMPLETE discussion/plan**, not just a one-line summary. This means:

- **Task title** — short one-line summary (as before)
- **Full plan** — below the title, include the complete solution/steps discussed. Use a blockquote or indented section with the detailed approach.
- **Key parameters** — URLs, API keys, account details, prices, etc. that were part of the discussion

**Format:**

```markdown
### N. Task Title
**方案（方案名）：**
- 步骤1：详细说明
- 步骤2：详细说明
- 注意：关键提示
```

**Example from this session:**

```markdown
### 4. 接家用PC的4080S跑本地Gemma + AI工作流
**方案：**
- 家用PC（Windows）已装Ollama，跑Gemma 21B
- 通过Tailscale从PVE的Hermes连过去调用
- 简单体力活（数据格式化/批量处理/文档提取）甩给Gemma干
- 预计节省15%-25% token消耗
- **延伸：AI多智能体工作流** — 详见 dedicated skill
```

**When the user asks to see a specific task**, read the full file and present the relevant entry with its complete plan — don't just read the title line.
