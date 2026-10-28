# Feishu (飞书) / Lark Ecosystem for AI Agents

## Three-Layer Agent Integration Architecture

Feishu open platform provides three composable capabilities for AI agent developers (as of May 2026):

### Layer 1: One-Click App Creation (Credential Layer)
- QR code scan to create a Lark/Feishu bot app with pre-configured permissions and event subscriptions
- Instantly obtain App ID / App Secret
- Goal: reduce "connect to Feishu" from hours to seconds
- SDK: Web QR Code SDK (Node.js, Python, Java, Go)

### Layer 2: Channel SDK (Interaction Layer)
- Real-time messaging in group chats, 1-on-1 chats, document comments
- Rich text, card messages, interactive buttons
- Integrates agent into Feishu conversations for send/receive

### Layer 3: Lark CLI (Business Operations Layer) ⭐
Open-source CLI tool (GitHub) that lets AI agents directly operate Feishu business objects:

| Capability | What it does |
|------------|-------------|
| Docs | Create, edit, read Feishu documents; collaborative editing |
| Base (多维表格) | Like Airtable — databases, kanban, tables |
| Calendar | Check schedules, create meetings, cross-timezone scheduling |
| Mail | Classify, process, reply to emails |
| Tasks | Create to-dos, assign tasks, track progress |
| Sheets | Read/write spreadsheets, data analysis |

### Typical Use Cases
1. **Post-meeting to-dos**: Auto-extract action items → create tasks → assign people
2. **Human-AI doc co-creation**: AI drafts → human annotates in Feishu → AI iterates
3. **Cross-timezone scheduling**: Auto-find free slots across multiple calendars
4. **Meeting data analysis**: Auto-compile meeting notes, stats
5. **Smart email triage**: Classification, priority sorting, auto-reply

## Hermes Integration

### Already Supported in Hermes
- **Feishu as messaging platform**: Listed in gateway supported platforms
- **`feishu_doc` toolset**: Feishu document tools (built into Hermes)
- **`feishu_drive` toolset**: Feishu drive tools (built into Hermes)
- **Feishu Plugin for OpenClaw**: Listed on Feishu open platform nav

### How to Connect
1. Create an app on Feishu Open Platform (open.feishu.cn)
2. Get App ID + App Secret
3. Configure in Hermes: `hermes gateway setup` → Feishu
4. Enable `feishu_doc` and `feishu_drive` toolsets: `hermes tools enable feishu_doc`

### Lark CLI Integration
- Lark CLI is open-source: can be installed and invoked via Hermes terminal tool
- Designed for any AI agent to call via command line
- Supports multi-profile configuration (multiple Feishu apps)
- Auth: `lark auth login` (app-level) + optional user authorization for personal data

### MCP Support
- Feishu open platform has an MCP User Guide section
- MCP integration allows agent to access Feishu tools as MCP server

## Key URLs
- Open Platform: https://open.feishu.cn
- Lark CLI docs: https://open.feishu.cn → Documentation → Lark CLI
- Hermes Feishu docs: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/
