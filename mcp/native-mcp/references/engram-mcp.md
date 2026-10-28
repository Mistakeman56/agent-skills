# Engram MCP — Persistent Memory Server

Engram is a Go-based persistent memory system exposed via MCP. Single binary, SQLite + FTS5.

- **GitHub**: [Gentleman-Programming/engram](https://github.com/Gentleman-Programming/engram) (⭐3,410)
- **Version installed**: 1.15.10
- **Binary**: `/usr/local/bin/engram`
- **Database**: `~/.engram/engram.db` (SQLite WAL mode)
- **MCP tools**: 19 (prefix `mcp_engram_*`)

## Config

```yaml
mcp_servers:
  engram:
    command: engram
    args:
      - mcp
      - "--tools=agent"
    timeout: 120          # 60 was too short — caused "unreachable" errors
```

## Tool List (19)

| Tool | Purpose |
|------|---------|
| `mem_save` | Save a memory with title, content, type |
| `mem_update` | Update existing memory |
| `mem_delete` | Delete a memory |
| `mem_search` | Search via FTS5 |
| `mem_context` | Recent session context |
| `mem_timeline` | Chronological context for an observation |
| `mem_get_observation` | Get specific observation by ID |
| `mem_suggest_topic_key` | Suggest topic keys |
| `mem_session_start` | Start a session (required before save via MCP) |
| `mem_session_end` | End a session |
| `mem_session_summary` | Summary of a session |
| `mem_judge` | Conflict judgment |
| `mem_compare` | Compare memories |
| `mem_save_prompt` | Save a prompt |
| `mem_capture_passive` | Passive capture |
| `mem_stats` | Statistics |
| `mem_current_project` | Current project info |
| `mem_merge_projects` | Merge projects |
| `mem_doctor` | Diagnostic check |

## Known Issues

### 1. CJK Search Not Working in CLI

The `engram search <query>` CLI uses FTS5 with the default `unicode61` tokenizer, which does **not** tokenize Chinese/Japanese/Korean text. Searching for "妈妈" returns zero results even when the data contains that text.

**Workarounds:**
- Use `engram export` to dump all memories as JSON, then grep
- Use MCP tools (`mcp_engram_mem_search`) which may use different query paths
- Store important facts with English keywords in the title for searchability
- File an upstream issue requesting CJK tokenizer support

### 2. Timeout Sensitivity

- `timeout: 60` in MCP config → intermittent "MCP server unreachable after 3 consecutive failures" errors during save/search
- `timeout: 120` → stable operation
- Root cause: the `engram mcp --tools=agent` process may need time for SQLite operations, especially WAL checkpointing

### 3. Session Required Before Save (MCP path)

When using MCP tools (not CLI), `mcp_engram_mem_session_start` must be called before `mcp_engram_mem_save`. The CLI (`engram save`) auto-creates a session.

### 4. No Knowledge Graph Model

Engram stores flat memory observations, not entity-relation graphs. For structured relational data (person A works_at company B), use the `mom-memory` skill's JSON data files instead.

## CLI Cheat Sheet

```bash
engram stats                          # Quick stats
engram search "keyword"              # Search (CJK-limited)
engram save "Title" "Content" --type learning  # Save memory
engram timeline <obs_id>             # View in context
engram export /tmp/dump.json         # Full export
engram context                       # Recent context
engram doctor                        # Diagnostic
engram tui                           # Interactive TUI
engram sync --cloud --project <name> # Cloud sync
```

## Session Lifecycle

```
engram session start --id <id> --directory <path>
  → auto-creates project from directory name
  → use project name in subsequent saves

engram save --project <name> "Title" "Content" --type <type>
  → creates/manual-save session if none active

engram stats sees "Sessions: N" with active + completed sessions
```

## When to use

Use engram for:
- Long-term memory that survives agent restarts
- Knowledge that should be searchable across sessions
- Data that doesn't need automatic context injection

Don't use engram for:
- Quick preferences (use MEMORY.md — auto-injected every turn)
- Step-by-step workflows (use Skills — loaded on demand)
- Mom's isolated memory (use mom-memory skill — separate namespace)
- Ephemeral conversation history (use session_search — full text)
