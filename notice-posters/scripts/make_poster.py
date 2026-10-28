# -*- coding: utf-8 -*-
"""生成海报/启事图片（HTML -> Playwright full_page 截图）

用法:
    python3 make_poster.py [名字] [电话] [照片路径] [特征描述] [丢失天数]
    省略的字段用占位符, 交付时列在“待补清单”里。

依赖: playwright + 系统 google-chrome + 已安装 CJK 字体
"""
import pathlib
import sys

OUT = pathlib.Path(__file__).resolve().parent.parent / "out"

# 已知信息: 改这里而不是改版式
KNOWN = {
    "age": "约 9 岁（成年猫）",
    "breed": "布偶猫 · 重点色（耳脸深灰棕 / 身体米白）",
    "lost_time": "2026年 9月 25日 夜间未归",
    "lost_place": "大连市某区 · 某小区别墅区",
    "note": "平时散养，常在自家院子活动，有院子的邻居请留意",
}

TEMPLATE = """<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1080px;background:#fff;color:#111;
     font-family:"Noto Sans CJK SC","WenQuanYi Zen Hei",sans-serif}}
.wrap{{border:14px solid #d32f2f;padding:44px 46px}}
h1{{text-align:center;font-size:96px;letter-spacing:14px;color:#d32f2f;
   font-weight:900;line-height:1;margin-bottom:8px}}
.sub{{text-align:center;font-size:34px;color:#d32f2f;letter-spacing:6px;
     margin-bottom:30px;font-weight:700}}
.photo{{width:100%;height:660px;border:6px solid #111;overflow:hidden;
       display:flex;align-items:center;justify-content:center;
       background:#f5f5f5;margin-bottom:34px}}
.photo img{{width:100%;height:100%;object-fit:cover}}
.ph{{font-size:56px;color:#999;text-align:center;line-height:1.6}}
.rows{{font-size:40px;line-height:1.75}}
.rows .r{{display:flex;border-bottom:3px solid #ddd;padding:14px 4px}}
.rows .k{{width:330px;color:#d32f2f;font-weight:800}}
.rows .v{{flex:1;font-weight:700}}
.time{{margin-top:30px;background:#d32f2f;color:#fff;padding:26px 30px;
      border-radius:14px}}
.time h3{{font-size:46px;font-weight:900;margin:0 0 12px;letter-spacing:3px}}
.time p{{font-size:38px;line-height:1.6;font-weight:700}}
.time p + h3{{margin-top:22px}}
.box{{margin-top:30px;border:5px solid #d32f2f;padding:26px 28px;border-radius:14px}}
.box h3{{font-size:42px;color:#d32f2f;margin-bottom:16px;font-weight:900}}
.box p{{font-size:38px;line-height:1.6;font-weight:600}}
.contact{{margin-top:30px;background:#111;color:#fff;padding:28px 30px;
         border-radius:14px;display:flex;justify-content:space-between;
         align-items:center}}
.contact .lab{{font-size:44px;font-weight:900;letter-spacing:4px}}
.contact .num{{font-size:74px;font-weight:900;color:#ffd54f;letter-spacing:4px}}
.thanks{{margin-top:26px;text-align:center;font-size:56px;font-weight:900;
        color:#d32f2f;letter-spacing:8px}}
.tip{{margin-top:18px;text-align:center;font-size:30px;color:#666;line-height:1.5}}
</style></head><body><div class="wrap">
  <h1>寻猫启事</h1>
  <div class="sub">家走丢了 · 求助</div>
  <div class="photo">{photo}</div>
  <div class="rows">
    <div class="r"><div class="k">名字</div><div class="v">{name}</div></div>
    <div class="r"><div class="k">品种 / 花色</div><div class="v">{breed}</div></div>
    <div class="r"><div class="k">年龄</div><div class="v">{age}</div></div>
    <div class="r"><div class="k">性别 / 是否绝育</div><div class="v">______</div></div>
    <div class="r"><div class="k">项圈 / 芯片</div><div class="v">______</div></div>
  </div>
  <div class="time">
    <h3>⏰ 走失时间</h3>
    <p>{lost_time} · 至今已 {days} 天</p>
    <p>{note}</p>
    <h3>📍 走失地点</h3>
    <p>{lost_place}</p>
  </div>
  <div class="box"><h3>🔍 外貌特征</h3><p>{features}</p></div>
  <div class="contact">
    <div class="lab">📞 联系电话</div><div class="num">{phone}</div>
  </div>
  <div class="thanks">重谢必有 · 万望相助</div>
  <div class="tip">如发现踪迹，请先拍照片 / 不要追赶，猫受惊会躲得更深</div>
</div></body></html>"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    name = sys.argv[1] if len(sys.argv) > 1 else "____"
    phone = sys.argv[2] if len(sys.argv) > 2 else "______"
    photo = sys.argv[3] if len(sys.argv) > 3 else ""
    features = sys.argv[4] if len(sys.argv) > 4 else "____________"
    days = sys.argv[5] if len(sys.argv) > 5 else "3"

    photo_html = (f'<img src="file://{photo}">' if photo
                  else '<div class="ph">猫的照片<br>待补</div>')

    html = TEMPLATE.format(
        photo=photo_html, name=name, phone=phone, features=features, days=days,
        **KNOWN,
    )

    hp = OUT / "notice.html"
    hp.write_text(html, encoding="utf-8")

    # 断言校验替换结果: 变量名写错时会静默产出废图
    assert "1080px" in html and "寻猫启事" in html, "模板结构不对"
    if photo:
        assert photo in html, "照片路径没进模板, 检查变量替换"

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox"])
        page = b.new_page(viewport={"width": 1080, "height": 1600})
        page.goto(f"file://{hp}")
        page.wait_for_timeout(500)
        png = OUT / "notice.png"
        page.screenshot(path=str(png), full_page=True)  # 必须 full_page, 否则裁掉底部
        b.close()

    print(f"{png}  ({png.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
