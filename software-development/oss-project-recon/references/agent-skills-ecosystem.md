# Agent Skill / 插件生态地图

用途：用户说"去 GitHub 逛逛，看看有没有优质的 skill"、"这个 harness 装什么好用"时，
先按本页定位生态，再用 SKILL.md 里的 5.2 判定可移植性。

> star / 插件数量 / 版本号都是**快照性质**，每次现场查（见主 SKILL.md Pitfall 2/14）。本页只记"是干什么的、怎么验、坑在哪"。

---

## 1. 三层概念，别混

| 层 | 是什么 | 能不能跨 harness |
|---|---|---|
| **harness** | agent 运行时/框架本体（dsh、Hermes、Claude Code、Codex、OpenClaw） | — |
| **plugin** | 绑死某个 harness 运行时的扩展（dsh 的 `dsh-plugin` topic、OpenClaw 插件） | ❌ 别家装不上 |
| **skill** | `SKILL.md`（`name` + `description` frontmatter）+ 可选 `references/`、`scripts/` | ✅ Agent Skills 标准，跨 harness |

**这个区分是回答的第一段。** 用户常把"插件生态"和"skill 生态"说成一件事；
照着错的层去推荐，会给出装不上的方案（例：把只支持 dsh 的 IM 接入插件推给 Hermes，
而 Hermes 自己已经有 weixin/wecom 通道）。

---

## 2. 主要 harness 与它们的检索入口

- **DeepSeek Harness（dsh）**：官方开源（MIT），"一切皆插件"，Cordis 架构。
  - 跑起来：`npx @deepseek-ai/dsh web` → 默认 `http://127.0.0.1:3080`
  - 找插件：GitHub topic `dsh-plugin`、`awesome-dsh-plugin/awesome-dsh-plugin`、`dsh-market/dsh-market`（可视化市场）
  - IM 接入：`xmanrui/dsh-im`（微信/企微/飞书/钉钉/QQ/Slack/Telegram/Discord/WhatsApp）——**plugin**
  - 定位：开发者预览期，官方自己写"会有破坏性变更"；跟 Hermes 是同层竞品，**不是可装的 skill 源**
- **Claude Code / Codex / OpenClaw**：各自有 plugin 目录，但它们的 **skills 目录是通用的**
- **跨 harness 检索**：GitHub topic `agent-skills`、`claude-skills`、`claude-code-skills`；
  以及 `SKILL.md` 字样直接搜。目录站（skills.sh、leaderboard、marketplace）只当索引

---

## 3. 已验证的优质 skill（按"能不能直接进 Hermes"排序）

### 第一梯队：可直接装、且内容验过

| 仓库 | 干什么 | 装法 | 注意 |
|---|---|---|---|
| `OthmanAdi/planning-with-files` | 文件化持久规划：`task_plan.md` / `findings.md` / `progress.md` 落盘，生命周期 hook 每轮注入，`/clear`、崩溃、压缩后计划还在 | 仓库自带 `.hermes/plugins/`，`hermes plugins install <repo>/.hermes/plugins/planning-with-files` 然后 `hermes plugins enable planning-with-files` | 原生支持 Hermes（frontmatter 里有 `metadata.hermes`），是这批里唯一"不需要改"的 |
| `blader/humanizer` | 去 AI 味改写：不是-x-而是-y 对比句、一行式收尾、三连排比、破折号滥用、假升华、销售腔。理论依据是维基百科 *Signs of AI writing* | 标准 skill，`~/.hermes/skills/humanizer/` | MIT、单文件、零依赖。写论文/材料/简历刚需 |
| `addyosmani/agent-skills` | 48 个生产级工程 skill：`context-engineering`、`planning-and-task-breakdown`、`code-review-and-quality`、`debugging-and-error-recovery`、`spec-driven-development`、`test-driven-development`、`code-simplification` | 按需挑单个目录拷进 `~/.hermes/skills/`，**别整仓全装**（同名概念会和既有 skill 撞） | 有 evals/、hooks/、AGENTS.md，工程素养高 |
| `rebelytics/one-skill-to-rule-them-all` | meta skill（`name: task-observer`）：干活时记录卡点/用户纠正，周期性复盘生成或改进 skill | 标准 skill | CC-BY-4.0。理念与 Hermes 的 `skill_manage` 一致，可互补 |
| `JimLiu/baoyu-skills` | 20 个中文向 skill：翻译、url→markdown、发公众号、幻灯片、信息图、markdown→html、youtube 逐字稿 | 挑单个目录 | 中文场景实用，但多数依赖它自己的 packages/，先读 SKILL.md 的依赖段 |

### 第二梯队：按需，先查重复

- `anthropics/skills`（官方）：`docx` / `pptx` / `xlsx` / `pdf` / `skill-creator` / `mcp-builder` / `canvas-design` 等。
  Hermes 已有同类 skill → **当参考实现读，别盲目覆盖**。
- `thedotmack/claude-mem`（跨会话持久上下文）：Hermes 已有 memory，功能重叠。
- `tt-a1i/archify`（想法/代码库 → 交互图）、`nexu-io/open-design`（设计 agent 工作区）。
- `browser-act/skills`（绕反爬的浏览器自动化）、`yusufkaraaslan/Skill_Seekers`（把文档站/PDF 转成 skill）。

### 噪音：别当成果交差

- `VoltAgent/awesome-agent-skills`、`ComposioHQ/awesome-claude-skills`、`travisvn/awesome-claude-skills`、
  `hesreallyhim/awesome-claude-code` 等 **awesome 列表**：只是目录，不含可装内容。
- `alirezarezvani/claude-skills` 这类**几百个 skill 的大合集**：量大质杂，逐个验的成本高于收益。
- 垂直党（网文写作、短剧分镜、中医辨证、CTF）：与用户场景无关就别占篇幅。

---

## 4. 交付形态（这个用户要的样子）

1. **先纠正概念**：plugin ≠ skill，一句话说清，并指出用户已有同类能力（避免重复建设）。
2. **第一梯队 3–4 个**，每个写：干什么 / 为什么对他有用 / **一条装法** / 一个注意点。
3. **第二梯队表格**一行一个，带"和已有功能是否重复"的判词。
4. **噪音单列**，明确"别浪费时间"。
5. **收尾给一个明确建议 + 一句确认**（"装 3 个就够，点头我就动手"），
   不要罗列五个方案让用户挑。

---

## 5. 装完必须验证（不能只报"已安装"）

1. `skills_list` 里能看到新 skill 的 `name` + `description`；
2. frontmatter 的 `description` 前 57 字符能独立触发（"Use when …"），否则后续会话不会加载它；
3. 对 plugin 类：`hermes plugins list` 状态为 enabled，再跑一次触发词确认真被注入；
4. 装失败的场景要如实报（缺依赖、要 Node 版本、要登录），**不要用"应该可以了"收尾**。
