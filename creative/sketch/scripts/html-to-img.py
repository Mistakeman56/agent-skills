#!/usr/bin/env python3
"""
HTML → PNG/JPEG using Playwright full-page screenshot.
Use this when Chrome headless --screenshot times out on long pages.

Usage:
  python3 scripts/html-to-img.py /path/to/file.html [output.jpg]

Requires: pip3 install playwright pillow
First run: playwright install chromium
"""
import sys, os
from playwright.sync_api import sync_playwright
from PIL import Image

html_path = sys.argv[1]
if not os.path.exists(html_path):
    print(f"File not found: {html_path}", file=sys.stderr)
    sys.exit(1)

out_path = sys.argv[2] if len(sys.argv) > 2 else html_path.replace('.html', '.jpg')
png_temp = out_path.replace('.jpg', '_temp.png').replace('.jpeg', '_temp.png')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 820, 'height': 800})
    page.goto('file://' + os.path.abspath(html_path))
    page.wait_for_timeout(3000)
    page.screenshot(path=png_temp, full_page=True)
    browser.close()

img = Image.open(png_temp)
img.save(out_path, 'JPEG', quality=88)
os.remove(png_temp)

print(f"OK: {out_path} ({os.path.getsize(out_path)} bytes, {img.size[1]}px tall)")
