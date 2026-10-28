# Hacker News Algolia API — Front Page in One Call

## Why This Matters

The official HN Firebase API requires **two calls per story** (one for `topstories.json`, then one per item). For a briefing that needs 10-15 stories, that's 11-16 API calls.

**The Algolia API returns all front-page stories in a single call**, with titles, URLs, points, comment counts, and author already included.

## Endpoint

```
GET https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=15
```

No authentication required. No rate limiting for moderate use.

## Usage

```bash
curl -s 'https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=15'
```

Response structure (`hits` array):
```json
{
  "hits": [
    {
      "title": "Elon Musk has lost his lawsuit against Sam Altman and OpenAI",
      "url": "https://techcrunch.com/...",
      "points": 720,
      "num_comments": 345,
      "author": "pseudolus",
      "objectID": "12345678",
      "created_at": "2026-05-18T14:00:00Z"
    },
    ...
  ]
}
```

Parsing in Python (use subprocess+curl to avoid proxy issues with urllib):
```python
import json, subprocess
r = subprocess.run(
    ['curl', '-s', '--noproxy', '*', 'https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=15'],
    capture_output=True, text=True
)
data = json.loads(r.stdout)
for hit in data['hits']:
    print(f"[{hit['points']} pts] {hit['title']}")
```

## Alternative: `hackerwebapp.com` (Redundant)

The existing reference mentions `api.hackerwebapp.com/news` as a single-call wrapper. That service returns the same data but with `time_ago` strings instead of timestamps. The Algolia API is the official backing service and is more reliable.

## Pitfalls

- **No `url` field for Ask HN / Show HN posts** — these are hosted on `news.ycombinator.com` and have `url` as `null`. Construct the link as `https://news.ycombinator.com/item?id={objectID}`.
- **Tag parameter is `tags=front_page` not `tags=frontpage`** — the latter returns no results.
- **`hitsPerPage` max is 1000** for pagination, but for briefings 10-20 is plenty.
- **Sort order** defaults to "by points" (relevance), which is exactly what you want — the most upvoted front-page stories first.
