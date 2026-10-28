#!/usr/bin/env python3
"""
API Balance Watchdog Template
Monitors API provider balance and alerts on change with emoji progress bars.
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
CACHE_FILE = os.path.expanduser("~/.hermes/.last_moonshot_balance")
CONFIG_FILE = os.path.expanduser("~/.hermes/config.yaml")

# Provider-specific settings
BALANCE_URL = "https://api.moonshot.cn/v1/users/me/balance"
API_KEY_PATTERN = r'model:\s*api_key:\s*([^\n]+)'  # Adjust regex for config.yaml layout
TOTAL_BUDGET = 20.0                  # Your monthly/quarterly budget for progress bar (set 0 to disable bar)

# For providers with tiered quotas (e.g., web free tier)
# Set these to known values if API exposes them; leave None if unknown
SMALL_QUOTA_TOTAL = None             # e.g., 1000 tokens / 10 conversations per 5h
LARGE_QUOTA_TOTAL = None             # e.g., 10000 tokens / 100 conversations per 7d
# ---------------------------------------------------------------------------


def load_api_key(config_path: str, pattern: str) -> str:
    with open(config_path) as f:
        content = f.read()
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        print("❌ 配置文件中未找到 API Key")
        sys.exit(1)
    return match.group(1).strip().strip('"').strip("'")


def emoji_bar(used: float, total: float, width: int = 10) -> str:
    """Return an emoji progress bar."""
    if total <= 0:
        return "🟦" * width + " ❓"
    ratio = min(used / total, 1.0)
    filled = int(ratio * width)
    empty = width - filled
    bar = "🟦" * filled + "⬜" * empty
    pct = ratio * 100
    if pct >= 90:
        bar += " 🔴"
    elif pct >= 70:
        bar += " 🟡"
    else:
        bar += " 🟢"
    return f"{bar}  {used:.1f}/{total:.1f} ({pct:.0f}%)"


def query_balance(url: str, key: str) -> dict:
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
    data = query_balance(BALANCE_URL, key)

    # --- Provider-specific parsing ---
    # Moonshot:
    available = float(data["data"]["available_balance"])
    cash = float(data["data"]["cash_balance"])
    voucher = float(data["data"]["voucher_balance"])
    current_value = available

    # DeepSeek (uncomment if needed):
    # bal = data["balance_infos"][0]
    # current_value = float(bal["total_balance"])
    # topped = float(bal["topped_up_balance"])
    # granted = float(bal["granted_balance"])

    # --- Cache comparison ---
    last = ""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            last = f.read().strip()

    if str(current_value) == last:
        sys.exit(0)  # No change, stay quiet

    # --- Update cache ---
    with open(CACHE_FILE, 'w') as f:
        f.write(str(current_value))

    # --- Output with visual progress bar ---
    print(f"💰 {PROVIDER_NAME} 额度变动")
    print("═" * 25)
    print(f"可用余额:  ¥{current_value:.2f}")
    if TOTAL_BUDGET > 0:
        consumed = max(0, TOTAL_BUDGET - current_value)
        print(f"消耗进度:  {emoji_bar(consumed, TOTAL_BUDGET)}")
    if voucher > 0:
        print(f"代金券:    ¥{voucher:.2f}")
    print("═" * 25)

    # Tiered quotas (only show if user provided values)
    if SMALL_QUOTA_TOTAL:
        print(f"小额度:    {emoji_bar(0, SMALL_QUOTA_TOTAL)}  (待实现: 需要 web 截取或手动输入已用量)")
    if LARGE_QUOTA_TOTAL:
        print(f"大额度:    {emoji_bar(0, LARGE_QUOTA_TOTAL)}  (待实现: 需要 web 截取或手动输入已用量)")
    if SMALL_QUOTA_TOTAL or LARGE_QUOTA_TOTAL:
        print("---")
        print("⚠️ API 不暴露 web 配额，以上进度条为设置上限后的占位符")

    print("---")
    print("下次余额变动会自动提醒")


if __name__ == "__main__":
    main()
