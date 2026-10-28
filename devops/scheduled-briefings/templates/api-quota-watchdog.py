#!/usr/bin/env python3
"""
API Organization Quota Watchdog Template
Monitors API provider organization-level token quotas and rate limits.
Alerts on change with emoji progress bars.
Copy and modify for specific providers.
"""
import json
import os
import sys
import urllib.request
import re

# ---------------------------------------------------------------------------
# CONFIG: modify for your provider
# ---------------------------------------------------------------------------
PROVIDER_NAME = "Moonshot"          # Display name
CACHE_FILE = os.path.expanduser("~/.hermes/.last_moonshot_quota")
CONFIG_FILE = os.path.expanduser("~/.hermes/config.yaml")

# Provider-specific settings
QUOTA_URL = "https://api.moonshot.cn/v1/users/me"
API_KEY_PATTERN = r'model:\s*api_key:\s*([^\n]+)'  # Adjust regex for config.yaml layout

# Which metrics to monitor and their display labels
# Format: (json_path, label, unit, alert_threshold_pct)
# json_path uses "/" to traverse nested dicts
METRICS = [
    ("organization/max_token_per_day", "organization_usage/cur_token_per_day", "📊 日 Token 限额", "tokens", 80),
    ("organization/max_token_quota", "organization_usage/cur_token_usage", "📊 总 Token 配额", "tokens", 80),
    ("organization/max_request_per_minute", "organization_usage/cur_request_per_minute", "🕐 RPM 限额", "req/min", 90),
    ("organization/max_concurrency", "organization_usage/cur_concurrency", "🔗 并发限额", "concurrent", 90),
]
# ---------------------------------------------------------------------------


def load_api_key(config_path: str, pattern: str) -> str:
    with open(config_path) as f:
        content = f.read()
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        print("❌ 配置文件中未找到 API Key")
        sys.exit(1)
    return match.group(1).strip().strip('"').strip("'")


def get_nested(data: dict, path: str):
    """Traverse nested dict using slash-separated path."""
    keys = path.split("/")
    for key in keys:
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            return None
    return data


def emoji_bar(used: float, total: float, width: int = 10) -> str:
    """Return an emoji progress bar showing consumption."""
    if total is None or total <= 0:
        return "🔲" * width + " ❌ 无限额数据"
    ratio = min(used / total, 1.0)
    filled = int(ratio * width)
    empty = width - filled
    bar = "🔵" * filled + "⚪" * empty
    pct = ratio * 100
    if pct >= 90:
        bar += " 🔴"
    elif pct >= 70:
        bar += " 🟡"
    else:
        bar += " 🟢"
    return f"{bar}  {used:,.0f}/{total:,.0f} ({pct:.1f}%)"


def query_quota(url: str, key: str) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        sys.exit(1)


def main():
    key = load_api_key(CONFIG_FILE, API_KEY_PATTERN)
    resp = query_quota(QUOTA_URL, key)

    if resp.get("code") != 0:
        print(f"❌ API 返回错误: {resp}")
        sys.exit(1)

    data = resp.get("data", {})

    # Build current state snapshot
    snapshot = {}
    lines = []
    alerts = []

    for limit_path, usage_path, label, unit, threshold in METRICS:
        limit = get_nested(data, limit_path)
        usage = get_nested(data, usage_path)

        if limit is not None:
            snapshot[limit_path] = limit
        if usage is not None:
            snapshot[usage_path] = usage

        if limit is not None and usage is not None:
            lines.append(f"{label}: {emoji_bar(usage, limit)}")
            pct = (usage / limit) * 100 if limit > 0 else 0
            if pct >= threshold:
                alerts.append(f"⚠️ {label}已达 {pct:.0f}%！")
        elif limit is not None:
            lines.append(f"{label}: 上限 {limit:,.0f} {unit} (当前用量未返回)")
        else:
            lines.append(f"{label}: 未知 (配置中未启用)")

    # --- Cache comparison ---
    snapshot_str = json.dumps(snapshot, sort_keys=True)
    last = ""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            last = f.read().strip()

    if snapshot_str == last:
        sys.exit(0)  # No change, stay quiet

    # --- Update cache ---
    with open(CACHE_FILE, 'w') as f:
        f.write(snapshot_str)

    # --- Output ---
    print(f"📊 {PROVIDER_NAME} 额度监控")
    print("═" * 30)
    for line in lines:
        print(line)
    if alerts:
        print("═" * 30)
        for alert in alerts:
            print(alert)
    print("─" * 30)
    print("下次额度变动会自动提醒")


if __name__ == "__main__":
    main()
