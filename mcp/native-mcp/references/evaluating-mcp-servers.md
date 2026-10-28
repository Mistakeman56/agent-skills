# Evaluating MCP Servers for Integration

## Decision Framework

When evaluating whether to install an MCP server, assess across these axes:

| Axis | Question | Red Flags |
|------|----------|-----------|
| **Function** | Does this do something we can't do already? | Overlap with existing tools |
| **Cost** | Free / API-key / self-hosted? | Paid SaaS for rarely-used feature |
| **Runtime** | npx/uvx/binary? Dependencies? | Heavy deps on resource-constrained hosts |
| **Reliability** | Stars, issues, maintenance cadence | Abandoned repo, stale releases, unresolved bugs |
| **China-accessibility** | Does the server or its API work behind GFW? | Hard-coded `r.jina.ai`, Google-only login, Cloudflare-hosted |
| **Data locality** | Where does data go? Self-hostable? | Required cloud with no self-host option |

## Case Study: Memory MCP Systems

This session evaluated memory persistence MCP servers. The comparison methodology is reusable.

### Candidates

| Server | Stars | Language | Storage | Key Differentiator |
|--------|-------|----------|---------|-------------------|
| `@modelcontextprotocol/server-memory` | (official) | TypeScript | JSONL (flat file) | Knowledge graph model, Anthropic official |
| **engram** | 3,410 (3mo old) | **Go** | **SQLite + FTS5** | 19 tools, full-text search, TUI, git/cloud sync |
| nocturne_memory | 1,055 | Python | SQLite/PG | Rollbackable, visual management UI |
| vestige | 527 | Rust | SQLite | FSRS spaced repetition, cognitive model |
| stash | 684 | **Go** | Postgres | Simple, single binary, episodes+facts model |

### Evaluation against our criteria

**memory-mcp (official):**
- ✅ NPM 321K downloads/mo — ecosystem-validated
- ✅ Knowledge graph model perfect for relational data (person A works_at company B)
- ❌ JSONL storage — linear search, slows with scale
- ❌ No search beyond basic entity name match
- ❌ No session management or memory compaction

**engram:**
- ✅ SQLite + FTS5 — sub-ms search at any scale
- ✅ 19 tools (save, search, timeline, session lifecycle, conflict detection)
- ✅ Single Go binary — zero deps, easy install
- ✅ TUI — can browse memory interactively
- ✅ Git/cloud sync for multi-machine setups
- ❌ No knowledge graph model (flat memory entries, not entity-relation)
- ❌ Community project, not Anthropic official
- ❌ Not specifically needed for our use case (Hermes built-in memory + session_search + skills already covers our needs)

**Decision:** Engram **is now installed** (v1.15.10, single Go binary `/usr/local/bin/engram`, SQLite DB at `~/.engram/engram.db`, MCP configured with `--tools=agent` flag). Used alongside Hermes native memory for long-term structured storage. See `references/engram-mcp.md` for integration details, known issues, and configuration.

### Real-world observations after integration

- **Timeout sensitivity**: `timeout: 60` caused intermittent "MCP server unreachable" errors on save/search. Bumped to `timeout: 120` and connectivity stabilized.
- **CJK search limitation**: `engram search` CLI uses FTS5 with default `unicode61` tokenizer which doesn't tokenize Chinese text. Searches for "妈妈" return no results even when data is present. Workaround: use `engram export` or MCP tools (`mcp_engram_mem_search`) which may use different query paths.
- **Session lifecycle**: `mcp_engram_mem_session_start` must be called before `mcp_engram_mem_save`. The CLI's `engram save` auto-creates a session.
- **Storage reliability**: SQLite with WAL mode, ACID transactions — survives agent crashes. Data verified via `engram export` after saves.

### Thinking Methodology for Future Evaluations

1. **Define the need first** — What exact capability is missing? Be concrete.
2. **Search candidates** — GitHub, NPM, awesome-mcp lists
3. **Filter by runtime fit** — Skim China-accessibility early
4. **Read source when in doubt** — Small servers can be audited in minutes
5. **Test in isolation** — Run with a single known-good call before integrating
6. **Benchmark against built-in** — Hermes already has: memory, cron, filesystem, search — don't add MCP that duplicates

## Case Study: Word/DOCX Editing MCP Servers

Evaluated for agent-driven Word document editing (creating, modifying, reviewing .docx files).

### Candidates

| Server | Stars | Lang | Runtime | Key Differentiator |
|--------|-------|------|---------|-------------------|
| **SecurityRonin/docx-mcp** | 22 | Python | `uvx docx-mcp-server` | Professional tracked changes, comments, template creation |
| **ykarapazar/word-mcp-live** | 129 | Python | `uvx --from word-mcp-live word_mcp_server` | 124 tools, live editing in open Word docs |
| GongRzhe/Office-Word-MCP-Server | 2,048 | Python | uvx/npx | ⚠️ **ARCHIVED** — no longer maintained |
| Aimino-Tech/opendocswork-mcp | 146 | Rust | cargo install | Multi-format (Word+Excel+PPT+PDF), fastest |
| alejandroBallesterosC/document-edit-mcp | 50 | Python | npx/smithery | Simple multi-format (Word+Excel+PDF) |

### Recommendation: Install Both docx-mcp + word-mcp-live

**docx-mcp** is the professional-grade choice:
- Native Word tracked changes (red strikethrough deletions, green underline insertions)
- Comments with add/reply/resolve
- Find & replace (text or regex) across body, footnotes, comments
- Create from templates (.dotx), markdown, or blank
- Tables, footnotes, headers/footers, images, sections, bookmarks
- Document protection (tracked-changes-only, read-only)
- 100% test coverage
- Install: `uvx docx-mcp-server`

**word-mcp-live** provides comprehensive coverage:
- 124 tools — most comprehensive Word MCP server
- Live editing — modifies documents while open in Word (Windows COM / macOS JXA)
- Per-action undo (each AI edit is individually reversible)
- Threaded comments, equations, cross-references, layout diagnostics
- Docker support for cross-platform
- Install: `uvx --from word-mcp-live word_mcp_server`
- **Note**: Live editing requires Word installed. Cross-platform mode works everywhere for batch processing.

**Why NOT the archived one:** GongRzhe/Office-Word-MCP-Server has 2,048 stars but is **archived** — no fixes, no security patches. docx-mcp is its spiritual successor with modern features.

### Installation on Remote Machines (SSH workflow)

Pattern for installing MCP servers on a remote machine (e.g., mimocode on MacBook):

```bash
# 1. SSH in
sshpass -p 'PASS' ssh user@HOST

# 2. Install uv (Python package manager) if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Test the MCP server
export PATH="$HOME/.local/bin:$PATH"
uvx docx-mcp-server          # stdio server, waits for JSON-RPC
uvx --from word-mcp-live word_mcp_server  # note: executable name differs from package name

# 4. Configure in agent's config (use Python to merge, NEVER heredoc!)
python3 -c "
import json
with open('CONFIG_PATH') as f: cfg = json.load(f)
cfg['mcpServers'] = {
    'docx-mcp': {'command': '/full/path/to/uvx', 'args': ['docx-mcp-server']},
    'word-mcp-live': {'command': '/full/path/to/uvx', 'args': ['--from', 'word-mcp-live', 'word_mcp_server']}
}
with open('CONFIG_PATH', 'w') as f: json.dump(cfg, f, indent=2)
"
```

**Pitfall**: `word-mcp-live` package provides executable `word_mcp_server` (underscore), not `word-mcp-live` (hyphen). Use `uvx --from word-mcp-live word_mcp_server`.

**Config format by agent:**
- **mimocode** (OpenCode schema): `~/.config/mimocode/config.json` → `"mcpServers": { ... }`
- **Claude Code**: `~/.claude.json` → project-level `"mcpServers": { ... }`
- **Hermes**: `~/.hermes/config.yaml` → `mcp_servers:` (YAML)

### Real-world observations

- **Tracked changes are native Word revisions**, not XML hacks — they show up correctly in Word's Review tab
- **Both servers use uvx** which auto-downloads dependencies on first run (~100-200MB cache). Subsequent runs are instant.
- **macOS system Python is 3.9.6** — too old for many MCP servers. uvx handles this by using its own Python 3.13.
- **Mimocode uses OpenCode config schema** (`$schema: https://opencode.ai/config.json`). MCP servers go in the root-level `mcpServers` key.

## Case Study: Local RAG MCP (mcp-local-rag)

Evaluated as a response to user request: "find a RAG vector database MCP on GitHub."

### Candidates

| Server | Stars | Lang | Runtime | Vector DB | Embedding | Notes |
|--------|-------|------|---------|-----------|-----------|-------|
| **shinpr/mcp-local-rag** | **256** 🔥 | **TypeScript** | **`npx -y mcp-local-rag`** | **LanceDB** (file-based) | **Transformers.js** (local) | **Winner** — zero setup, no API key, works offline |
| alejandro-ao/RAG-MCP | 6 | Python | `python src/main.py` | ChromaDB | Sentence Transformers | Needs LlamaParse API key for PDF |
| wesleygriffin/pdfrag | ~10 | Python | `python server.py` | ChromaDB | sentence-transformers | PDF-focused but less active |

### Winner: shinpr/mcp-local-rag (256⭐)

**Why it won:**

| Criterion | mcp-local-rag | alejandro-ao/RAG-MCP |
|-----------|---------------|----------------------|
| ⭐ Community | 256 stars, 34 releases, active | 6 stars, 16 commits |
| 🚀 Setup | `npx -y mcp-local-rag` (one line) | Python venv + pip install + LlamaParse API key |
| 🏠 Privacy | Fully local, no data leaves machine | LlamaParse sends docs to cloud |
| 💰 Cost | **Free** (model download once, ~90MB) | Free + LlamaParse API credits |
| 📄 PDF | ✅ Via mupdf | ✅ Via LlamaParse (but needs API key) |
| 🌏 Chinese | ✅ Multilingual model available (`onnx-community/embeddinggemma-300m-ONNX`) | Requires LlamaParse for Chinese PDF |
| 🔍 Search | Hybrid (semantic + keyword boost) | Pure semantic |
| 🔋 Offline | ✅ After first model download | ❌ Needs LlamaParse API online |
| 🧠 Embedding | Local Transformers.js (no GPU needed) | Local Sentence Transformers |

**Key features discovered:**
- **Smart semantic chunking** — splits by topic boundaries, not character count (better for technical docs)
- **Keyword boost** — exact terms like `useEffect` or error codes rank higher (excellent for code/docs)
- **Quality filtering** — groups by relevance gaps instead of arbitrary top-K cutoffs
- **Supports:** PDF, DOCX, TXT, MD, HTML
- **7 MCP tools:** `ingest_file`, `ingest_data`, `query_documents`, `read_chunk_neighbors`, `list_files`, `delete_file`, `status`
- **Agent Skills available** — install with `npx mcp-local-rag skills install --<client>`
- **~1.2s query speed** for 10K chunks on M1 MacBook Pro

**Token impact analysis:**
- Each `query_documents` call injects ~2-5K tokens of context (only relevant chunks)
- No token cost for embedding (runs locally)
- Zero overhead per turn — only called when user asks question that triggers search
- Estimated +10-20% token overhead per relevant query

**Caveats:**
- Requires `BASE_DIR` env var set to document root
- First run downloads ~90MB model (1-2 min)
- Switching embedding model requires re-ingesting all documents
- Not suitable for multi-user scenarios

**Deployment plan for this environment:**
```yaml
# ~/.hermes/config.yaml snippet
mcp_servers:
  local-rag:
    command: "npx"
    args: ["-y", "mcp-local-rag"]
    env:
      BASE_DIR: "~/.hermes/rag-docs"
      # Optional: multilingual model for Chinese docs
      # MODEL_NAME: "onnx-community/embeddinggemma-300m-ONNX"
    timeout: 120
```

Then create data dir and ingest docs:
```bash
mkdir -p ~/.hermes/rag-docs
cp /path/to/course-pdfs/*.pdf ~/.hermes/rag-docs/
# Start a new session — tools auto-discovered at startup
```

## Quick Reference: Popular MCP Server Categories

| Category | Top Picks | Notes |
|----------|-----------|-------|
| **RAG / Vector DB** | **shinpr/mcp-local-rag** (⭐256) | **Best local-first RAG** — npx one-liner, LanceDB, offline, supports Chinese. See case study above. |
| **Memory** | engram (⭐3.4K) > memory-mcp (official) | See case study above |
| **Search** | Bright Data MCP (⭐2.3K, free 5K/mo) | Best China-accessibility option; jina blocked by Cloudflare |
| **Smart Home** | gehaiyi/xiaomi-home-mcp (⭐2.3K) | 60+ Mijia devices controllable |
| **Code Intelligence** | codebase-memory-mcp (⭐2.2K) | 155 langs, sub-ms queries, single static binary |
| **Maps** | amap-maps-mcp-server | China-only, no Google Maps dependency |
| **Web Scraping** | playwright/mcp | Full browser automation via SSH bridge |
| **Word/DOCX editing** | **docx-mcp** (⭐22) + **word-mcp-live** (⭐129) | **Best combo**: docx-mcp for professional tracked-changes/comments; word-mcp-live for 124 tools + live editing. See case study below. |
| **Documents** | context7-mcp | Free real-time docs for popular frameworks |
