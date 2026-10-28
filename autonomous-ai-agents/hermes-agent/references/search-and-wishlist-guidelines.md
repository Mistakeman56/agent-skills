# Search Preference & Wishlist Management

## Search Tool Preference (User-Formalized)

**User's exact instruction (2026-05-16):** "以后我说让你去搜你就去brightdata和GitHub等权威网站搜"

**Rule:** When the user asks to search for something, ALWAYS use:
1. **BrightData** (`mcp_brightdata_brightdata_invoke_tool` with `search_engine`) for general web searches — returns clean Google/Bing/Yandex results
2. **GitHub** (`mcp_fetch` on `github.com/search` or `github.com/topics`) for code/project searches
3. **Do NOT use Baidu** — its robots.txt blocks automated agents and returns no useful data

This was a two-step correction:
- First user said "你用那个bright搜，别用百度" (use BrightData, not Baidu)
- Later formalized: "以后我说让你去搜你就去brightdata和GitHub等权威网站搜"

## Wishlist / Todo List Management

The user requested a persistent todo/wishlist stored at `~/.hermes/wishlist.md`.

**Format:**
- Priority tiers: 🔴高 → 🟡中 → 🟢低
- Each entry: Task name + **complete actionable plan** (not just a title)
- Include full discussion details: URLs, addresses, phone numbers, prices, steps
- Update with `write_file` (full rewrite) or `patch` (targeted edits)

**Trigger phrases:**
- User says "存到待办" / "记在待办" / "加到待办清单" → save immediately with full details
- User says "我的待办清单" / "我还有什么没做的" → read and display the file
- User says "XXX做完了" / "划掉" → mark as done

**Critical rule:** Do NOT just save a short note like "之前说过的，记上了". Always search past conversations first to get the complete plan before saving. The user explicitly corrected this: "你不仅要把什么事存进去，还要把我们讨论的方案都完整存进去"
