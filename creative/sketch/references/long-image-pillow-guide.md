# Pillow 长图生成参考

## 适用场景
信息卡、攻略图、对比表、教程长图等超过一屏的内容。Chrome headless 截图对长页面容易超时，Pillow 更稳定。

## 关键模式

### 1. 字体准备
```python
FONT_R = '/usr/share/fonts/noto-cjk/NotoSansCJKsc-Regular.otf'
FONT_B = '/usr/share/fonts/noto-cjk/NotoSansCJKsc-Bold.otf'
fs = {
    'r12': ImageFont.truetype(FONT_R, 12),
    'r14': ImageFont.truetype(FONT_R, 14),
    'r15': ImageFont.truetype(FONT_R, 15),
    'r16': ImageFont.truetype(FONT_R, 16),
    'b14': ImageFont.truetype(FONT_B, 14),
    'b15': ImageFont.truetype(FONT_B, 15),
    'b16': ImageFont.truetype(FONT_B, 16),
    'b20': ImageFont.truetype(FONT_B, 20),
    'b22': ImageFont.truetype(FONT_B, 22),
    'b24': ImageFont.truetype(FONT_B, 24),
    'b26': ImageFont.truetype(FONT_B, 26),
    'b30': ImageFont.truetype(FONT_B, 30),
    'b34': ImageFont.truetype(FONT_B, 34),
}
```

### 2. 全局变量 + 累进 y 坐标
```python
W = 820
H = 4200  # 预分配足够高度
img = Image.new('RGB', (W, H), '#0f0a1e')
y = 0

def sp(h=12):
    global y; y += h
```

### 3. 卡片函数封装
```python
def card(title, items, tint=WHITE, icon=''):
    global y
    sp(4)
    h = 20 + max(len(items), 1) * 28 + 8
    d.rounded_rectangle([(24, y), (W-24, y+h)], radius=10, fill=CARD, outline=BORDER)
    y += 14
    d.text((44, y), f'{icon} {title}', fill=tint, font=fs['b22'])
    y += 36
    for item in items:
        if item.startswith('>'):  # 标题行
            d.text((60, y), item[1:], fill=GOLD, font=fs['b15'])
        elif item.startswith('!'):  # 警告
            d.text((60, y), item[1:], fill=RED, font=fs['r14'])
        else:  # 普通正文
            d.text((60, y), item, fill=MUTED, font=fs['r15'])
        y += 28
    y += 12
```

### 4. 节标题
```python
def section_title(emoji, title):
    global y
    sp(20)
    d.line([(28, y), (W-28, y)], fill=GOLD, width=2)
    y += 14
    d.text((36, y), f'{emoji}  {title}', fill=GOLD, font=fs['b26'])
    y += 42
```

### 5. 带编号的步骤卡片
```python
def step_card(steps):
    global y
    sp(4)
    total_h = 20 + sum(52 for _ in steps) + 8
    d.rounded_rectangle([(24, y), (W-24, y+total_h)], radius=10, fill=CARD, outline=BORDER)
    y += 16
    for i, (label, desc) in enumerate(steps):
        cx, cy = 52, y+12
        d.ellipse([(cx-14, cy-14), (cx+14, cy+14)], fill=GOLD, outline='#1a1040')
        d.text((cx, cy), str(i+1), fill='#1a1035', font=fs['b16'], anchor='mm')
        d.text((78, y), label, fill=WHITE, font=fs['b15'])
        d.text((78, y+22), desc, fill=MUTED, font=fs['r14'])
        y += 52
    y += 8
```

### 6. 最终裁剪
```python
# 裁掉预分配的多余空白
img2 = img.crop((0, 0, W, y))
img2.save('~/.hermes/cache/output.jpg', 'JPEG', quality=85)
```

## 避坑
1. `rounded_rectangle` 在 Pillow 8.0+ 可用，老版本可能需要手动画圆角
2. 字体要预先 `fc-list :lang=zh` 确认存在
3. 颜色值用 16 进制字符串（`'#0f0a1e'`），Pillow 自动解析
4. 预分配高度（H）至少为最终高度的 1.3 倍，最后 crop
5. 输出 JPEG quality=85 平衡大小和画质，供微信发送通常 <400KB
