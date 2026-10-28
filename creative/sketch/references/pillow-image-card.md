# Python Pillow Image Card Generation

当用户要求「把这段内容生成图片」时——生成对比表、信息卡、摘要卡片等静态 PNG 图片。

## 为什么用 Pillow 而不是浏览器截图

- ✅ Pillow 通常已安装（`from PIL import Image, ImageDraw, ImageFont`）
- ✅ 无需下载 Chrome/Chromium/Playwright（国内网络慢，易出沙箱/DBus 错误）
- ✅ 纯 Python 可控，生成的 PNG 可直接通过 `MEDIA:/path/to/file` 发送
- ❌ Playwright MCP 服务器可能在远程机器上运行，安装浏览器非常麻烦

## 快速模板：对比表卡片

```python
from PIL import Image, ImageDraw, ImageFont
import os

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
# 中文用:
# FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
# 安装: apt-get install -y fonts-noto-cjk 或 wget 下载

OUTPUT = "~/.hermes/cache/comparison.png"
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

W, H = 860, 1000
img = Image.new("RGB", (W, H), "#0f0a1e")
draw = ImageDraw.Draw(img)
font_s = ImageFont.truetype(FONT_PATH, 13)
font_m = ImageFont.truetype(FONT_PATH, 15)
font_l = ImageFont.truetype(FONT_BOLD, 22)

# --- 标题 ---
draw.text((36, 28), "Kiro vs VS Code + Kimi Code", fill="#ffffff", font=font_l)

# --- 画分隔线 ---
y = 76
draw.line([(36, y), (W-36, y)], fill="rgba(255,255,255,0.08)")

# --- 表格 header ---
cols = [180, 300, 320]  # x offsets for each column
headers = ["维度", "VS Code + Kimi Code", "Kiro"]
for x, h in zip(cols, headers):
    draw.text((x, y+10), h, fill="rgba(255,255,255,0.35)", font=font_s)

y += 36

# --- 表格行 ---
rows_data = [
    ("形态", "VS Code + 插件", "独立 IDE"),
    ("AI 模型", "Kimi 自家", "Claude Sonnet 4"),
    ("定价", "~¥30/月", "当前免费，正式$20/月"),
]
for label, col1, col2 in rows_data:
    draw.text((cols[0], y+6), label, fill="rgba(255,255,255,0.5)", font=font_s)
    draw.text((cols[1], y+6), col1, fill="rgba(255,255,255,0.8)", font=font_s)
    draw.text((cols[2], y+6), col2, fill="#6ee7b7", font=font_s)
    y += 36

img.save(OUTPUT)
print(f"Saved to {OUTPUT}")
```

## 深色主题颜色调色板

| 用途 | 颜色 | 说明 |
|------|------|------|
| 背景 | `#0f0a1e` | 深紫黑色 |
| 卡片区域 | `rgba(255,255,255,0.04)` | 半透明白 |
| 主标题 | `#ffffff` | 白色 |
| 正文 | `rgba(255,255,255,0.8)` | ~80% 白 |
| 副标题/表头 | `rgba(255,255,255,0.35)` | 35% 白 |
| 高亮(正) | `#6ee7b7` | 翠绿色 |
| 高亮(警) | `#fbbf24` | 琥珀色 |
| 边框 | `rgba(255,255,255,0.06)` | 极淡白 |

## 中文字体问题（核心坑）

**这是 Pillow 做图翻车率最高的问题** — Pillow 遇到中文字体缺失不会报错，只会画出空白/方块。

### 正确的检查流程

```bash
# 第1步：检查系统是否有中文字体
fc-list :lang=zh 2>/dev/null | head -5
# 如果没有输出 → 需要安装

# 第2步：安装中文字体
# ❌ 不要 apt-get install fonts-noto-cjk（~80MB，国内网络常超时）
# ✅ 用 wget 下载单个字体文件（~16MB，速度快）
cd /tmp
wget -q "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf" \
  -O /usr/local/share/fonts/NotoSansCJKsc-Regular.otf
wget -q "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Bold.otf" \
  -O /usr/local/share/fonts/NotoSansCJKsc-Bold.otf
fc-cache -f

# 第3步：确认安装成功
fc-list :lang=zh | head -3
# 应输出: Noto Sans CJK SC:style=Regular
```

### 如果 Pillow 搞不定，立即切换方案

当以下任一情况出现时：
- 中文字体安装失败
- 排版效果不理想（Pillow 的 layout 能力有限）
- 需要复杂排版（多列、渐变、圆角阴影等）

→ **立刻切换到 HTML + Chrome headless 截图方案**：

```bash
# 1. 写单文件 HTML（支持完整 CSS 排版）
write_file("/tmp/card.html", "<!DOCTYPE html><html>...")

# 2. 确认字体已安装（同上 fc-list 流程）

# 3. Chrome 截图
google-chrome --headless --disable-gpu --no-sandbox \
  --screenshot=~/.hermes/cache/card.png \
  --window-size=800,HEIGHT \
  file:///tmp/card.html

# 4. 发送
MEDIA:~/.hermes/cache/card.png
```

HTML+CSS 方案的优势：
- ✅ 完整 CSS 排版（flex, grid, 圆角, 渐变, 阴影）
- ✅ 比 Pillow 更易调试和修改
- ✅ Chrome 通常已安装（`/usr/bin/google-chrome`）
- ✅ 截图质量高

## 完整示例

参考 `scripts/comparison-card.py` — 可用于生成的完整脚本（含对比表布局、颜色方案、深色主题）。
