#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中国旅行攻略信息图生成模板（PIL + Noto CJK，已验证可出图 1080px 宽）。
2026-08 以杭州3日攻略实战验证；用户两次纠正：emoji 不渲染、固定画布截断底部。

用法：
  1. 修改 FONT 常量（若服务器字体路径不同）
  2. 把 days 列表换成目标城市的内容（title / items[(名称,描述)] / tip）
  3. python3 generate_travel_guide_image.py   → 输出 /root/travel_guide.png

铁律：
  - 不要用 emoji（Noto CJK 无彩色表情，显示为空白/方框），用 ◆ · | 等文本符号
  - 必须两遍法：先估算 total_h 再建画布，否则底部内容被裁剪
"""
from PIL import Image, ImageDraw, ImageFont

FONT_REG = "/usr/share/fonts/noto-cjk/NotoSansCJKsc-Regular.otf"
FONT_BOLD = "/usr/share/fonts/noto-cjk/NotoSansCJKsc-Bold.otf"

W = 1080
MARGIN = 60
CONTENT_W = W - MARGIN * 2

BG = (250, 248, 242)
TITLE = (30, 60, 50)
ACCENT = (0, 120, 100)
ACCENT2 = (200, 100, 40)
CARD = (255, 255, 255)
TEXT = (50, 50, 50)
SUBTEXT = (120, 120, 120)
LINE = (220, 225, 218)


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def draw_wrapped(d, x, y, text, fnt, fill=TEXT, max_w=CONTENT_W - 60, spacing=8):
    """逐字换行绘制，返回新的 y。"""
    lines, cur = [], ""
    for ch in text:
        test = cur + ch
        if d.textlength(test, font=fnt) > max_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = test
    lines.append(cur)
    yy = y
    for ln in lines:
        d.text((x, yy), ln, font=fnt, fill=fill)
        yy += fnt.size + spacing
    return yy


# ===== 数据（示例：杭州3日；换成目标城市内容即可） =====
days = [
    {
        "title": "Day 1  |  西湖经典环湖（免费为主）",
        "items": [
            ("◆ 断桥残雪", "白娘子传说地，龙翔桥地铁站步行可达"),
            ("◆ 白堤 - 孤山", "一路湖光山色，中山公园打卡十景石碑"),
            ("◆ 三潭印月", "1元人民币背面取景地，游船登岛55元/人"),
            ("◆ 雷峰塔", "登塔俯瞰全景（40元/人），白蛇传说"),
        ],
        "tip": "提示：全天免费环湖，傍晚湖滨看喷泉",
    },
    {
        "title": "Day 2  |  灵隐祈福 + 龙井茶山",
        "items": [
            ("◆ 灵隐寺+飞来峰", "千年古刹香火最旺（联票75元/人）"),
            ("◆ 龙井村", "乾隆御茶园，村口茶农喝龙井"),
            ("◆ 九溪烟树", "溪水潺潺森林氧吧，夏日避暑玩水"),
        ],
        "tip": "提示：灵隐寺早点去避人流，九溪可穿拖鞋玩水",
    },
]

f_title = font(36, True)
f_item_name = font(30, True)
f_item_desc = font(26)
f_tip = font(27, True)


def card_height(items):
    h = 100
    for _name, desc in items:
        desc_lines = 1
        if f_item_desc.getlength(desc) > CONTENT_W - 90:
            desc_lines = 2
        h += f_item_name.size + 14 + f_item_desc.size * desc_lines + 18
    h += 70
    return h


def main():
    # ===== 第一遍：估算总高度 =====
    total_h = 40 + 130
    for day in days:
        total_h += card_height(day["items"]) + 24
    total_h += 150 + 24 + 100 + 40

    img = Image.new("RGB", (W, total_h), BG)
    d = ImageDraw.Draw(img)

    # ===== 顶部 =====
    y = 40
    d.rectangle([0, 0, W, 12], fill=ACCENT)
    d.text((MARGIN, y), "杭州 3 日游攻略", font=font(58, True), fill=TITLE)
    y += 85
    d.text((MARGIN, y), "示例标题  |  日期  |  双人版", font=font(30), fill=ACCENT)
    y += 52
    d.line([MARGIN, y, W - MARGIN, y], fill=LINE, width=2)
    y += 28

    # ===== 卡片 =====
    for day in days:
        h = card_height(day["items"])
        d.rounded_rectangle([MARGIN, y, W - MARGIN, y + h], radius=18, fill=CARD, outline=LINE, width=2)
        d.rounded_rectangle([MARGIN + 18, y + 18, MARGIN + 26, y + h - 18], radius=4, fill=ACCENT)

        yy = y + 30
        d.text((MARGIN + 50, yy), day["title"], font=f_title, fill=ACCENT)
        yy += f_title.size + 22

        for name, desc in day["items"]:
            d.text((MARGIN + 50, yy), name, font=f_item_name, fill=TEXT)
            yy += f_item_name.size + 14
            yy = draw_wrapped(d, MARGIN + 78, yy, desc, f_item_desc, fill=SUBTEXT, max_w=CONTENT_W - 90)
            yy += 18

        d.text((MARGIN + 50, yy), day["tip"], font=f_tip, fill=ACCENT2)
        y += h + 24

    # ===== 底部 =====
    budget_h = 150
    d.rounded_rectangle([MARGIN, y, W - MARGIN, y + budget_h], radius=18, fill=(240, 248, 245), outline=ACCENT, width=2)
    yy = y + 20
    d.text((MARGIN + 30, yy), "预算（双人）", font=font(32, True), fill=ACCENT)
    yy += 50
    d.text((MARGIN + 30, yy), "门票 + 吃饭 + 交通 约 1150 元", font=font(28), fill=TEXT)
    yy += 46
    d.text((MARGIN + 30, yy), "酒店建议西湖湖滨汉庭 250元/晚，提前订", font=font(28), fill=TEXT)
    y += budget_h + 24

    img = img.crop((0, 0, W, y + 10))
    img.save("/root/travel_guide.png", "PNG")
    print("saved /root/travel_guide.png", img.size)


if __name__ == "__main__":
    main()
