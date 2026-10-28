#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPTV 分片时延/抖动探针 —— 判断「能播但偶尔卡」是不是源站侧。

用法:
    python3 iptv_jitter_probe.py '<订阅URL | 频道m3u8>' \
        [--ua 'okHttp/Mod-1.5.0.0'] [--channels 3] [--segments 4] [--buffer 3.0]

判读: 最慢分片耗时 > 播放器缓冲 ⇒ 必然冻帧。

设计要点:
  * 输出里所有 URL 的 query 一律打码，绝不打印订阅 token/sign/userid。
  * 订阅会自动挑几个「台名前缀不同」的频道，因为同类频道往往同源、测一个就够。
  * 分片按顺序串行下载（模拟播放器行为），抖动 = max - min，比平均值更能预测卡顿。
"""
import argparse
import re
import ssl
import statistics
import sys
import time
import urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def mask(url):
    """把 query 抹掉，防止订阅凭证进日志。"""
    return re.sub(r"\?.*$", "?***", url or "")


def fetch(url, ua, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        data = r.read()
    return data, time.time() - t0


def parse_playlist(text):
    """返回 [(台名, 地址)]；非 m3u 内容返回空表。"""
    out, name = [], None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            m = re.search(r",(.+)$", line)
            name = m.group(1).strip() if m else "?"
        elif line.startswith("http") and name:
            out.append((name, line))
            name = None
    return out


def pick_channels(chans, limit):
    """按台名前缀去重，尽量挑不同类型的台。"""
    seen, picked = set(), []
    for name, url in chans:
        key = re.split(r"[-_\s]", name)[0].strip()
        if key in seen:
            continue
        seen.add(key)
        picked.append((name, url))
        if len(picked) >= limit:
            break
    return picked


def first_variant(text, base):
    """master playlist 会指向子 m3u8；跟一层。"""
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and ".m3u8" in line:
            return line if line.startswith("http") else base + "/" + line
    return None


def probe_channel(name, url, ua, nseg, timeout):
    print(f"── {name[:30]} ──")
    print(f"   地址 {mask(url)}")
    base = url.rsplit("/", 1)[0]
    try:
        body, ttfb = fetch(url, ua, timeout)
        text = body.decode("utf-8", "ignore")
    except Exception as exc:
        print(f"   m3u8 拉取失败: {type(exc).__name__} {exc}\n")
        return None

    nested = first_variant(text, base)
    if nested:
        print(f"   master playlist → 跟子列表 {mask(nested)}")
        try:
            body, ttfb = fetch(nested, ua, timeout)
            text = body.decode("utf-8", "ignore")
            base = nested.rsplit("/", 1)[0]
        except Exception as exc:
            print(f"   子列表失败: {type(exc).__name__}\n")
            return None

    segs = [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    print(f"   m3u8 TTFB {ttfb * 1000:.0f} ms，{len(text)} 字节，{len(segs)} 个分片")
    if not segs:
        print("   没有分片地址，跳过\n")
        return None

    seg = segs[0] if segs[0].startswith("http") else base + "/" + segs[0]
    times, sizes = [], []
    for i in range(nseg):
        try:
            data, dt = fetch(seg, ua, timeout)
            times.append(dt)
            sizes.append(len(data))
        except Exception as exc:
            print(f"   分片{i + 1} 失败: {type(exc).__name__}")
    if not times:
        print("   所有分片都失败\n")
        return None

    avg, worst = statistics.mean(times), max(times)
    jitter = worst - min(times)
    size = statistics.mean(sizes) if sizes else 0
    mbps = size * 8 / avg / 1e6 if avg > 0 else 0
    flag = "  ← 抖动大，最容易卡" if jitter > 0.5 else ""
    print(
        f"   分片 x{len(times)}: 平均 {avg * 1000:.0f} ms  最慢 {worst * 1000:.0f} ms  "
        f"大小 {size / 1024:.0f} KB  折算 {mbps:.1f} Mbps"
    )
    print(f"   抖动 {jitter * 1000:.0f} ms{flag}\n")
    return {"name": name, "ttfb": ttfb, "worst": worst, "jitter": jitter, "mbps": mbps}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="订阅地址或频道 m3u8")
    ap.add_argument("--ua", default="okHttp/Mod-1.5.0.0")
    ap.add_argument("--channels", type=int, default=3)
    ap.add_argument("--segments", type=int, default=4)
    ap.add_argument("--buffer", type=float, default=3.0, help="播放器缓冲秒数")
    ap.add_argument("--timeout", type=float, default=15.0)
    args = ap.parse_args()

    try:
        body, ttfb = fetch(args.url, args.ua, args.timeout)
    except Exception as exc:
        print(f"拉取失败: {type(exc).__name__} {exc}")
        return 1
    text = body.decode("utf-8", "ignore")

    chans = parse_playlist(text)
    results = []
    if chans:
        print(f"订阅拉取 {ttfb * 1000:.0f} ms，共 {len(chans)} 个频道\n")
        for name, url in pick_channels(chans, args.channels):
            r = probe_channel(name, url, args.ua, args.segments, args.timeout)
            if r:
                results.append(r)
    else:
        r = probe_channel("（直接给定的频道）", args.url, args.ua, args.segments, args.timeout)
        if r:
            results.append(r)

    if not results:
        print("没有任何频道测出结果。")
        return 1

    print("=" * 56)
    print(f"{'频道':<20}{'TTFB':>9}{'最慢分片':>11}{'抖动':>10}")
    for r in results:
        print(
            f"{r['name'][:18]:<20}{r['ttfb'] * 1000:>7.0f}ms"
            f"{r['worst'] * 1000:>9.0f}ms{r['jitter'] * 1000:>8.0f}ms"
        )
    print("=" * 56)

    worst = max(results, key=lambda r: r["worst"])
    if worst["worst"] > args.buffer:
        print(
            f"⚠ {worst['name'][:20]} 最慢分片 {worst['worst'] * 1000:.0f} ms "
            f"已超过缓冲 {args.buffer * 1000:.0f} ms ⇒ 这个台必然冻帧。"
        )
        print("   处置顺序：缓冲调到 6~8 s → 避开抖动大的台 → 换响应更快的源。")
    else:
        print(
            f"✓ 最慢分片 {worst['worst'] * 1000:.0f} ms 在缓冲 {args.buffer * 1000:.0f} ms 之内，"
            "源站时延不是卡顿主因，另找播放端/本地网络。"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
