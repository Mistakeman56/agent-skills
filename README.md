# Agent Skills Collection

> 一套给 AI Agent 用的可复用技能库（Hermes Agent skills），共 **124 个 skill**，覆盖 **19 个领域**。

## 这是什么

每个 skill 是一个目录，内含 `SKILL.md`（YAML frontmatter + Markdown 正文），说明：

- **什么时候该用它**（`description` 字段 —— agent 靠这一行决定是否加载）
- **具体怎么做**（命令、API 端点、参数含义、踩过的坑）
- **可选附件**：`references/`（深入文档）、`scripts/`（可直接执行的脚本）、`templates/`、`assets/`

设计思路是 **渐进式加载**：agent 平时只看到所有 skill 的 description（一行字），
判断相关时才加载全文，避免把全部知识一次性塞进上下文。

## 目录结构

```
.
├── README.md
├── LICENSE
└── <category>/
    └── <skill-name>/
        ├── SKILL.md          # 必需：frontmatter + 正文
        ├── references/       # 可选：深入文档
        └── scripts/          # 可选：可直接执行的脚本
```

## 怎么用

**在 Hermes Agent 里**

```bash
cp -r <category>/<skill-name> ~/.hermes/skills/
```

重启 session 后 agent 会自动发现。

**其他 agent 框架**

`SKILL.md` 是纯 Markdown + YAML，任何支持渐进式技能加载的框架都能直接用；
也可以把 `references/` 当技术手册单独阅读。

## 分类索引

### AI 代理编排（2）

| Skill | 说明 |
|---|---|
| [`hermes-agent`](autonomous-ai-agents/hermes-agent/) | Configure, extend, or contribute to Hermes Agent. |
| [`merge-reconciler`](autonomous-ai-agents/merge-reconciler/) | Neutral third-party resolution of agent merge conflicts. |

### 创意与视觉（13）

| Skill | 说明 |
|---|---|
| [`architecture-diagram`](creative/architecture-diagram/) | Dark-themed SVG architecture/cloud/infra diagrams as HTML. |
| [`ascii-art`](creative/ascii-art/) | ASCII art: pyfiglet, cowsay, boxes, image-to-ascii. |
| [`baoyu-comic`](creative/baoyu-comic/) | Knowledge comics (知识漫画): educational, biography, tutorial. |
| [`comfyui`](creative/comfyui/) | Generate images, video, and audio via diffusion workflows. |
| [`creative-ideation`](creative/creative-ideation/) | Generate project ideas via creative constraints. |
| [`excalidraw`](creative/excalidraw/) | Hand-drawn Excalidraw JSON diagrams (arch, flow, seq). |
| [`p5js`](creative/p5js/) | p5.js sketches: gen art, shaders, interactive, 3D. |
| [`pixel-art`](creative/pixel-art/) | Pixel art w/ era palettes (NES, Game Boy, PICO-8). |
| [`pretext`](creative/pretext/) | Build creative browser demos with DOM-free text layout. |
| [`sketch`](creative/sketch/) | Throwaway HTML mockups: 2-3 design variants to compare. |
| [`touchdesigner-mcp`](creative/touchdesigner-mcp/) | Control TouchDesigner via twozero MCP. |
| [`web-overlay-animation`](creative/web-overlay-animation/) | Use when 复刻网页/视频特效，或做浮在真实页面上的动画层。 |
| [`web-visual-demos`](creative/web-visual-demos/) | Use when replicating or building a web visual effect demo. |

### 数据科学（1）

| Skill | 说明 |
|---|---|
| [`jupyter-live-kernel`](data-science/jupyter-live-kernel/) | Iterative Python via live Jupyter kernel (hamelnb). |

### 运维与网络（17）

| Skill | 说明 |
|---|---|
| [`a-share-simulated-trading`](devops/a-share-simulated-trading/) | Set up and operate A-share (Chinese stock market) simulated trading via the eastmoney MX MCP server. |
| [`game-hang-triage`](devops/game-hang-triage/) | Use when 游戏卡住/冻结/黑屏/失去响应。先按 GPU-DXGI 层定性，再恢复对局。 |
| [`game-latency-triage`](devops/game-latency-triage/) | Use when 游戏不跟手/手感延迟高但游戏内 ping 与帧率都正常——分层定性，路由器侧常驻采样。 |
| [`hermes-gateway-ops`](devops/hermes-gateway-ops/) | Use when Hermes gateway is down, flapping, or stuck. |
| [`home-public-services`](devops/home-public-services/) | Use when the user 发布内网服务到公网（加网站/映射MC/改端口/查访问故障）。 |
| [`kanban-orchestrator`](devops/kanban-orchestrator/) | Decomposition playbook + anti-temptation rules for an orchestrator profile routing work through Kanban. |
| [`kanban-worker`](devops/kanban-worker/) | Pitfalls, examples, and edge cases for Hermes Kanban workers. |
| [`lan-offline-triage`](devops/lan-offline-triage/) | Use when 内网设备离线/ping 不通（摄像头、NAS、IoT）——路由器侧取证定层，再修消费端。 |
| [`openclash-user-guide`](devops/openclash-user-guide/) | Use when 排查/配置 OpenClash 或 Mihomo — 按路由表读子文档，先调试日志。 |
| [`pt-connectivity-triage`](devops/pt-connectivity-triage/) | Use when PT站连接性为否、种子tracker报错、入站端口不通、公网IP变动影响绑定服务时排查。 |
| [`pve-administration`](devops/pve-administration/) | Proxmox VE & homelab infrastructure administration: VM/LXC lifecycle, storage management, Clash/OpenClash |
| [`ruijie-ac-api`](devops/ruijie-ac-api/) | the user asks about 锐捷AC漫游/信道/AP状态时用，读 SSH 关闭的锐捷设备配置。 |
| [`scheduled-briefings`](devops/scheduled-briefings/) | Set up automated recurring cron jobs that deliver multi-source daily briefings (GitHub trending, news, pr |
| [`sdlc-review`](devops/sdlc-review/) | Review Kanban handoffs and route verified outcomes. |
| [`self-hosted-service-deploy`](devops/self-hosted-service-deploy/) | Use when 给家里 PVE 加一个自建 Web 服务。 |
| [`selfhosted-service-ops`](devops/selfhosted-service-ops/) | Use when 部署/备份/核对自建服务（密码库类）。 |
| [`webhook-subscriptions`](devops/webhook-subscriptions/) | Webhook subscriptions: event-driven agent runs. |

### 邮件（1）

| Skill | 说明 |
|---|---|
| [`email-inbox-triage`](email/email-inbox-triage/) | Triage an inbox: prioritize threads, draft replies safely. |

### 游戏（2）

| Skill | 说明 |
|---|---|
| [`minecraft-modpack-server`](gaming/minecraft-modpack-server/) | Host modded Minecraft servers (CurseForge, Modrinth). |
| [`pokemon-player`](gaming/pokemon-player/) | Play Pokemon via headless emulator + RAM reads. |

### 硬件选型（4）

| Skill | 说明 |
|---|---|
| [`android-bootloader-unlock`](hardware/android-bootloader-unlock/) | Use when the user 问旧手机能否刷机/解锁 bootloader。 |
| [`android-flashing-feasibility`](hardware/android-flashing-feasibility/) | Use when 判断安卓手机能不能刷机/解 bootloader、能刷什么 ROM。 |
| [`custom-mechanical-keyboard`](hardware/custom-mechanical-keyboard/) | 客制化机械键盘搭配/改装建议（毕业级配置、麻将音、陶瓷键帽、金属套件、轴体选择、夜魔改装）。当用户问键盘搭配、键帽/轴体/套件品牌、改装方案时使用。核心理论：闷润沉麻将音三标准、陶瓷键帽市场（山海贵vs御极/隅 |
| [`das-storage-hardware`](hardware/das-storage-hardware/) | Use when the user 选型/评估/组装硬盘笼、DAS、JBOD 外置存储——线材风道、到手验收。 |

### MCP 协议（1）

| Skill | 说明 |
|---|---|
| [`native-mcp`](mcp/native-mcp/) | MCP client: connect servers, register tools (stdio/HTTP). |

### 媒体处理（6）

| Skill | 说明 |
|---|---|
| [`heartmula`](media/heartmula/) | HeartMuLa: Suno-like song generation from lyrics + tags. |
| [`image-analysis`](media/image-analysis/) | 分析用户发来的图片/PDF页/视频（照片、截图、笔记、菜单、录屏）。视觉模型一律以 config.yaml → auxiliary.vision 为准（勿硬编码模型名）；工具集没暴露 vision 工具时直连该 |
| [`iptv-playlist-triage`](media/iptv-playlist-triage/) | Use when IPTV 直播源打不开/全台同画面/能播但卡顿。 |
| [`iptv-source-troubleshooting`](media/iptv-source-troubleshooting/) | Use when 直播源在播放器里看不了/黑屏/全台同一画面。先查UA。 |
| [`spotify`](media/spotify/) | Spotify: play, search, queue, manage playlists and devices. |
| [`video-clip-publishing`](media/video-clip-publishing/) | Use when the user wants live-clip → B站 auto-publish pipelines. |

### 记忆管理（1）

| Skill | 说明 |
|---|---|
| [`hermes-memory-maintenance`](memory/hermes-memory-maintenance/) | Use when editing, renaming, pruning Hermes memory entries. |

### MLOps（10）

| Skill | 说明 |
|---|---|
| [`audiocraft`](mlops/audiocraft/) | AudioCraft: MusicGen text-to-music, AudioGen text-to-sound. |
| [`dspy`](mlops/dspy/) | DSPy: declarative LM programs, auto-optimize prompts, RAG. |
| [`evaluating-llms-harness`](mlops/evaluating-llms-harness/) | lm-eval-harness: benchmark LLMs (MMLU, GSM8K, etc.). |
| [`huggingface-hub`](mlops/huggingface-hub/) | HuggingFace hf CLI: search/download/upload models, datasets. |
| [`llama-cpp`](mlops/llama-cpp/) | llama.cpp local GGUF inference + HF Hub model discovery. |
| [`local-ai-workstation`](mlops/local-ai-workstation/) | >- |
| [`obliteratus`](mlops/obliteratus/) | OBLITERATUS: abliterate LLM refusals (diff-in-means). |
| [`segment-anything`](mlops/segment-anything/) | SAM: zero-shot image segmentation via points, boxes, masks. |
| [`serving-llms-vllm`](mlops/serving-llms-vllm/) | vLLM: high-throughput LLM serving, OpenAI API, quantization. |
| [`weights-and-biases`](mlops/weights-and-biases/) | W&B: log ML experiments, sweeps, model registry, dashboards. |

### 生产力与文档（23）

| Skill | 说明 |
|---|---|
| [`box`](productivity/box/) | Box manages cloud files, sharing, search, and metadata. |
| [`china-domestic-travel-planning`](productivity/china-domestic-travel-planning/) | 中国国内多城市旅行规划（机票/高铁比价、酒店区域选择、多人预算分配）。覆盖携程机票JSON API、12306高铁API、高德MCP查酒店、行程表格化与预算表编制。用户有频繁国内出行需求（上海-苏州-杭州等）。 |
| [`cn-consumer-dispute-escalation`](productivity/cn-consumer-dispute-escalation/) | Use when the user faces a Chinese carrier plan or refund dispute. |
| [`deferred-task-tracker`](productivity/deferred-task-tracker/) | Track deferred, long-term, or 'can't do right now' tasks for the user in a persistent wishlist file. |
| [`document-to-action-items`](productivity/document-to-action-items/) | Extract cited obligations, deadlines, tasks from documents. |
| [`docx`](productivity/docx/) | Create, read, edit, template, and review Word .docx files. |
| [`interrupted-work-resume`](productivity/interrupted-work-resume/) | Use when 用户说刚才的活/进度没了（会话被重置或切了上下文）——从会话库接回断点并实测核实。 |
| [`linear`](productivity/linear/) | Linear: manage issues, projects, teams via GraphQL + curl. |
| [`meeting-action-items`](productivity/meeting-action-items/) | Turn meeting notes into cited decisions, owners, tickets. |
| [`nano-pdf`](productivity/nano-pdf/) | Edit text in existing PDFs via natural-language prompts. |
| [`ocr-and-documents`](productivity/ocr-and-documents/) | Convert documents to Markdown for LLM consumption (markitdown, pymupdf, marker-pdf). |
| [`pdf`](productivity/pdf/) | PDF files: create, read, merge, fill, OCR, edit text. |
| [`pdf-page-ops`](productivity/pdf-page-ops/) | 删/挑/合并 PDF 页面，并在交付前核验。用户要求删改 PDF 页时使用。 |
| [`personal-investing`](productivity/personal-investing/) | Use when the user 问定投/基金/场内 ETF/投多少钱/家庭应急金/长期理财规划。 |
| [`petdex`](productivity/petdex/) | Install and select animated petdex mascots for Hermes. |
| [`poster-image`](productivity/poster-image/) | Use when making a Chinese poster or guide image. |
| [`product-price-monitor`](productivity/product-price-monitor/) | Watch product, flight, or listing prices; alert on target. |
| [`resume-writing`](productivity/resume-writing/) | Use when the user 写简历/项目经历/自我介绍 — 按他的结构与措辞红线一次成型。 |
| [`session-librarian`](productivity/session-librarian/) | Organize sessions by prompt: find, rename, archive, prune. |
| [`slide-deck-authoring`](productivity/slide-deck-authoring/) | Use when building a .pptx deck or its speech script from source material. |
| [`stirling-pdf`](productivity/stirling-pdf/) | Use when OCR、压缩、转换或归档 PDF。 |
| [`weekly-review-planning`](productivity/weekly-review-planning/) | Weekly reset: commitments, stalled work, next-week plan. |
| [`xlsx`](productivity/xlsx/) | Create, read, edit Excel .xlsx workbooks and CSVs. |

### 红队测试（1）

| Skill | 说明 |
|---|---|
| [`godmode`](red-teaming/godmode/) | Jailbreak LLMs: Parseltongue, GODMODE, ULTRAPLINIAN. |

### 调研与检索（11）

| Skill | 说明 |
|---|---|
| [`blogwatcher`](research/blogwatcher/) | Monitor blogs and RSS/Atom feeds via blogwatcher-cli tool. |
| [`competitor-news-monitor`](research/competitor-news-monitor/) | Watch named companies for material news; cited digests. |
| [`consumer-tech-briefing`](research/consumer-tech-briefing/) | Use when the user asks about a tech product/launch/model. |
| [`deepseek-search-fetch`](research/deepseek-search-fetch/) | Use when 要中文网页搜索或抓网页正文。ds-web CLI。 |
| [`grounded-citations`](research/grounded-citations/) | Ground answers and documents in cited, verifiable sources. |
| [`hot-topic-evaluation`](research/hot-topic-evaluation/) | Use when the user asks to evaluate a hot topic, viral event, or to fact-check a forwarded claim. |
| [`knowledge-rag-ingestion`](research/knowledge-rag-ingestion/) | Use when: 1) 用户要求调研/研究某个技术领域并存入RAG知识库; 2) 用户发来文档要求整理入库; 3) 回答中发现知识缺口需自动补全。执行四阶段Pipeline：Research Planning |
| [`niche-china-brand-research`](research/niche-china-brand-research/) | 调研小众/新兴中国消费品牌（客制化外设、新消费、白牌 vs 头部品牌）能否买——用 Exa 查圈内社区、电商图文、行业媒体，交叉验证真实存在性、价格区间、工艺/质量坑。用户常做此类购买决策调研（陶瓷键帽、车、键 |
| [`polymarket`](research/polymarket/) | Query Polymarket: markets, prices, orderbooks, history. |
| [`research-paper-writing`](research/research-paper-writing/) | Write ML papers for NeurIPS/ICML/ICLR: design→submit. |
| [`vpn-airport-research`](research/vpn-airport-research/) | Use when the user 要买/换/比价 VPN 或机场订阅、查官网套餐。含隐晦措辞与官网验真规则。 |

### 通用（18）

| Skill | 说明 |
|---|---|
| [`a-stock-data`](root/a-stock-data/) | A股全栈数据工具包 — 覆盖行情(腾讯)、研报(东财)、信号(同花顺热点+龙虎榜+行业排名+北向)、新闻(东财+财联社)等HTTP接口。mootdx(TCP)需国内IP。iwen cai需API Key。与ea |
| [`canvas-game-dev`](root/canvas-game-dev/) | Use when building or debugging a single-file HTML5 canvas game (render loop, camera, projectiles, procedu |
| [`cli-anything`](root/cli-anything/) | >- |
| [`coding-agents`](root/coding-agents/) | Delegate coding tasks to autonomous CLI agents (Claude Code, Codex, OpenCode). |
| [`comfyui-deployment`](root/comfyui-deployment/) | Windows 装 ComfyUI、修 GGUF/CUDA 出图报错时用。 |
| [`hermes-model-failover`](root/hermes-model-failover/) | Use when a Hermes model call refuses or fails. |
| [`home-energy-audit`](root/home-energy-audit/) | Use when the user 要排查家庭电费异常、统计设备功耗、或把国家电网用电数据接进 Home Assistant。 |
| [`invoice-forwarder`](root/invoice-forwarder/) | Monitor Agent Mail inbox for invoice emails, download PDF attachments, and forward to user via WeChat. |
| [`local-agent-ollama`](root/local-agent-ollama/) | Use when connecting local Ollama to Claude Code agents. |
| [`local-dns`](root/local-dns/) | Use when DNS fails or domains stop resolving. |
| [`moviepilot`](root/moviepilot/) | probe |
| [`nav-monitor`](root/nav-monitor/) | Use when the user 问内网入口网站/三设备监控状态，或要改 nav 页面、排查数据不刷新。 |
| [`notice-posters`](root/notice-posters/) | Use when making a poster, notice, or flyer image. |
| [`officecli`](root/officecli/) | Create, analyze, proofread, and modify Office documents (.docx, .xlsx, .pptx) using the officecli CLI too |
| [`pc-remote-ops`](root/pc-remote-ops/) | Use when running commands on the user's Windows PC over SSH — Git Bash is the DEFAULT shell (2026-10-09), |
| [`speedtest-triage`](root/speedtest-triage/) | Use when 测速异常(测速软件/裸下载都测不出宽带)——四层定性：劫持/GeoIP/附属/出口限速。 |
| [`uncensored-model-scouting`](root/uncensored-model-scouting/) | 找去审查/abliterated 模型并按显卡显存选型部署时用。 |
| [`yuanbao`](root/yuanbao/) | Yuanbao (元宝) groups: @mention users, query info/members. |

### 智能家居（3）

| Skill | 说明 |
|---|---|
| [`home-assistant-admin`](smart-home/home-assistant-admin/) | Use when the user 要接入或设计 Home Assistant（MCP 连通、仪表盘与实体筛选、摄像头/监控流接入）。 |
| [`miloco-perception`](smart-home/miloco-perception/) | Monitor and troubleshoot the Miloco perception engine on CT <ID>/PVE — correct CLI commands, service heal |
| [`openhue`](smart-home/openhue/) | Control Philips Hue lights, scenes, rooms via OpenHue CLI. |

### 社交媒体（1）

| Skill | 说明 |
|---|---|
| [`xurl`](social-media/xurl/) | X/Twitter via xurl CLI: raw post search, posting, DM, media. |

### 软件开发（7）

| Skill | 说明 |
|---|---|
| [`apk-analysis`](software-development/apk-analysis/) | Analyze Android APK files — extract metadata, check architecture compatibility, parse UniApp/web-app mani |
| [`github`](software-development/github/) | GitHub via gh CLI: PRs, issues, reviews, repos, auth. |
| [`inspecting-hermes-desktop-dom`](software-development/inspecting-hermes-desktop-dom/) | Read the live Hermes desktop DOM/CSS over CDP. |
| [`oss-project-recon`](software-development/oss-project-recon/) | Use when verifying what an OSS project really can do. |
| [`plan`](software-development/plan/) | Write a markdown plan to .hermes/plans/; no execution. |
| [`subagent-driven-development`](software-development/subagent-driven-development/) | Execute plans via delegate_task subagents (2-stage review). |
| [`writing-plans`](software-development/writing-plans/) | Write implementation plans: bite-sized tasks, paths, code. |

### 网页抓取（2）

| Skill | 说明 |
|---|---|
| [`blocked-page-recovery`](web/blocked-page-recovery/) | Use when a fetch fails: 403/429, paywall, WAF, bot wall. |
| [`cn-blocked-api-access`](web/cn-blocked-api-access/) | Use when a China network cannot reach a host or API. |

## 隐私

本仓库在发布前经过多轮脱敏，**不含任何可识别个人或环境的信息**：

### 技术信息

| 内容 | 处理 |
|---|---|
| 内网 / 公网 IP | `192.0.2.x` / `203.0.113.1`（RFC 5737 文档保留地址） |
| 域名 | `example.com` |
| Tailscale 地址 | `100.64.0.1` |
| 密码 / Token / API Key | `<PASSWORD>` / `<API_KEY>` |
| 用户名 / 主机名 | `user` / `MYPC` |
| 本机路径 | `~/.hermes` |
| MAC 地址 | `00:00:00:00:00:00` |
| 设备序列号 / 设备 ID | `<DEVICE_ID>` |

### 个人信息

| 内容 | 处理 |
|---|---|
| 昵称 / 姓名 | 全部移除，改中性表述 |
| 学校 / 单位 / 税号 | 移除 |
| 班级名单、学号 | 整个 skill 移除 |
| 个人交易记录、持仓明细 | 全部移除 |
| 备考计划、目标院校 | 全部移除 |
| 家庭成员、住址、车辆 | 移除或改中性表述 |

**保留的只有方法**：命令怎么写、坑在哪、参数什么含义。
所有示例中的地址、账号、路径均为占位符，替换成本地值即可使用。

## 说明

- 内容来自真实运维 / 开发过程的沉淀，为可读性保留了具体场景，不影响按步骤复现
- 部分 skill 依赖特定工具（`gh`、`docker`、`pct`、`curl` 等），环境不具备时按需安装
- 涉及系统配置的 skill（防火墙、网络、存储）**执行前务必理解每一步**，不要照抄

## License

MIT — 见 [LICENSE](LICENSE)。

_最后更新：2026-10-28_
