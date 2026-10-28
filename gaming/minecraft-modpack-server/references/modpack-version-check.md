# Checking Modpack Version Updates on GitHub

## When to Use
- User asks "有没有新版本" or "出了什么新版本" for their modpack
- Need to compare current server version (from server files) with latest GitHub release
- Need changelog details to decide whether to upgrade

## Workflow

### 1. Find the Modpack Repository

Search GitHub for the modpack name:

```bash
# Use GitHub MCP search
mcp_github_github_invoke_tool(tool_name="search_repositories", tool_input={"query": "GregTech Odyssey GT Odyssey", "order": "desc", "per_page": 5, "sort": "stars"})
```

The official repository is typically the one with the most stars and "modpack" in the description.

### 2. Check Releases Page

```bash
# Scrape the releases page
mcp_brightdata_scrape_as_markdown(url="https://github.com/ORG/REPO/releases")
```

Look for:
- Latest version tag (e.g., `0.5.5`, `v2.3.0`)
- Release date
- Whether it's stable, beta, or alpha

### 3. Get Detailed Changelog

Many modpacks link to a separate wiki/changelog page. Look for URLs in the release notes:

```text
✨(Major Update!) 0.5.5-Beta Changelog: https://gtodyssey.com/article/zh/54
```

Use BrightData to scrape this page for full details.

### 4. Compare With Current Server Version

On the server:

```bash
# For GregTech Odyssey / GT-based packs:
# The version is in the core mod jar filename
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- ls <server_dir>/mods/ | grep -i gtocore"
# Example output: gtocore-0.5.4.jar

# For other modpacks, check the mods directory or a version file:
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- ls <server_dir>/mods/ | grep -i core"
```

### 5. Present Update Assessment

When presenting the findings, structure as:

```
## Modpack X.Y.Z Update Report

**Current:** X.Y.Z → **Latest:** A.B.C (released DATE)

### 🔥 Key Changes
- Bullet point major additions
- Bug fixes relevant to current playthrough
- ⚠️ Breaking/incompatible changes (highlight these!)

### ⚠️ Compatibility Warning
- Which configs/ME networks/machines might break
- Whether updating mid-playthrough is safe
- Backup requirement reminder

### 💡 Recommendation
- "更新吧，修复了很多bug" or "先别更，不兼容变更太多"
```

## Common Sources for Changelogs by Modpack

| Modpack | Changelog Location |
|---------|-------------------|
| GregTech Odyssey (GTO) | `https://gtodyssey.com/article/zh/54` + GitHub Releases |
| All the Mods (ATM) | GitHub Releases + CF page |
| GregTech New Horizons (GTNH) | GitHub Releases + forum thread |
| FTB packs | FTB wiki + GitHub Releases |

## Pitfalls
- **Release notes may be auto-generated from commits** — look for a manually written summary section at the top
- **Beta tags may have patch subversion** (e.g., `0.5.5-beta` is actually `0.5.5-beta-patch2`) — check the release description body, not just the tag name
- **Chinese modpack changelogs** may be on Chinese-only websites (gtodyssey.com, bilibili, mcmod.cn) — use BrightData to scrape as markdown
- **Version numbering isn't always sequential** — check release dates, not just version numbers, to determine what's newer
- **Big version jumps may skip intermediate pre-releases** — the changelog from the official site may include all Pre1~Pre4 changes even though only the final beta was released
