#!/usr/bin/env python3
"""无头验证网页视觉演示：控制台报错 + 度量探针 + 全页/放大截图 + 可选录屏。

用法:
  python3 verify_web_demo.py <url|file://...> [--probe probe.js] [--zoom SELECTOR]
                            [--shot out.png] [--zoom-out z.png] [--record DIR]
                            [--wait 3000] [--width 1000] [--height 1000]

--probe 指向一个 JS 文件（形如 `() => ({...})`，返回可 JSON 化的对象），在页面里 evaluate
        后打印 —— 度量指标写在那里：脚到最近文本框的距离中位数 / 随时间采样的 planted 数 /
        膝关节角 / 某只脚两个时刻的位移。这几个数字才是「真的踩在字上、真的在动」的证据。
--zoom  给个选择器（例如主体层 `#bodyLayer > g`），脚本取其 bbox 外扩 ~130px、
        device_scale_factor=2 截图 —— **放大图才是判断小特征在不在的依据**（全页图会把
        <10px 的细节判成「不存在」：眼睛、关节、有没有压在字上都会被误判）。
--record 指定目录则录屏（webm），之后转 mp4 交付：
        ffmpeg -i x.webm -vf scale=1000:1000,fps=30 -c:v libx264 -crf 21 \
               -pix_fmt yuv420p -movflags +faststart demo.mp4

退出码：0 = 无页面报错；1 = 有 pageerror。
"""
import argparse, asyncio, glob, json, os, sys


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--probe")
    ap.add_argument("--zoom")
    ap.add_argument("--shot", default="/tmp/webdemo_full.png")
    ap.add_argument("--zoom-out", default="/tmp/webdemo_zoom.png")
    ap.add_argument("--record")
    ap.add_argument("--wait", type=int, default=3000)
    ap.add_argument("--width", type=int, default=1000)
    ap.add_argument("--height", type=int, default=1000)
    a = ap.parse_args()

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx_kw = {"viewport": {"width": a.width, "height": a.height}}
        if a.record:
            os.makedirs(a.record, exist_ok=True)
            ctx_kw.update(record_video_dir=a.record,
                          record_video_size={"width": a.width, "height": a.height})
        ctx = await b.new_context(**ctx_kw)
        pg = await ctx.new_page()
        errs, con_errs = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: con_errs.append(m.text) if m.type == "error" else None)
        await pg.goto(a.url, wait_until="load")
        await pg.wait_for_timeout(a.wait)

        print("pageerror:", errs if errs else "none OK")
        if con_errs:
            print("console.error:", con_errs[:5])

        if a.probe:
            js = open(a.probe).read()
            try:
                print("probe:", json.dumps(await pg.evaluate(js), ensure_ascii=False, indent=2))
            except Exception as e:  # noqa: BLE001
                print("probe FAILED:", e)

        await pg.screenshot(path=a.shot)
        print("full shot:", a.shot, os.path.getsize(a.shot), "bytes")

        if a.zoom:
            box = await pg.evaluate(
                """(sel) => { const el = document.querySelector(sel); if (!el) return null;
                     const r = el.getBoundingClientRect();
                     return {x: r.left, y: r.top, width: r.width, height: r.height}; }""",
                a.zoom,
            )
            if box:
                m = 130
                zx = max(0, box["x"] - m)
                zy = max(0, box["y"] - m)
                zw = max(40, min(a.width - zx, box["width"] + 2 * m))
                zh = max(40, min(a.height - zy, box["height"] + 2 * m))
                ctx2 = await b.new_context(viewport={"width": a.width, "height": a.height},
                                           device_scale_factor=2)
                pg2 = await ctx2.new_page()
                await pg2.goto(a.url, wait_until="load")
                await pg2.wait_for_timeout(a.wait)
                await pg2.screenshot(path=a.zoom_out,
                                     clip={"x": zx, "y": zy, "width": zw, "height": zh})
                await ctx2.close()
                print("zoom shot:", a.zoom_out, os.path.getsize(a.zoom_out), "bytes")
            else:
                print("zoom: selector not found ->", a.zoom)

        await ctx.close()  # flushes the video
        await b.close()

    if a.record:
        for f in glob.glob(os.path.join(a.record, "*.webm")):
            print("video:", f, os.path.getsize(f), "bytes")
    return 1 if errs else 0


sys.exit(asyncio.run(main()))
