#!/usr/bin/env python3
"""iLink (Weixin bot) 凭证只读探活 / read-only iLink bot credential probe.

用途：判断某个 iLink bot 的会话还活着还是已经过期（"绑定失效"）
  ret=None errcode=None            -> ✅ 会话正常
  errcode=-14 'session timeout'    -> ❌ 已死，必须重新扫码
  ret=-2 'unknown error'/空        -> ⚠️ stale-session 信号

安全设计 / safety:
  * 走 ilink/bot/getupdates，带上磁盘上现存的 get_updates_buf
  * 原始响应**原样落盘** /tmp/ilink_probe_<bot_id>.json，**不推进 sync 游标**
    => 不会吞掉待收消息，也不会破坏后续正式接入时的游标
  * 纯读操作，不发送任何消息

用法:
  python3 ilink_bot_probe.py                        # 扫描 ~/.hermes/weixin/accounts/*.json
  python3 ilink_bot_probe.py <bot_id> [<bot_id>...] # 指定 bot 身份
  HERMES_HOME=~/.hermes python3 ilink_bot_probe.py

依赖: aiohttp（用 hermes 自带 venv:
  ~/.hermes/hermes-agent/venv/bin/python 跑本脚本最保险）
"""
import asyncio
import base64
import glob
import json
import os
import secrets
import ssl
import struct
import sys

ILINK_BASE_URL = "https://ilinkai.weixin.qq.com"
ILINK_APP_ID = "bot"
CHANNEL_VERSION = "2.2.0"
ILINK_APP_CLIENT_VERSION = (2 << 16) | (2 << 8) | 0
HERMES_HOME = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
ACCOUNTS_DIR = os.path.join(HERMES_HOME, "weixin", "accounts")


def _uin():
    return base64.b64encode(str(struct.unpack(">I", secrets.token_bytes(4))[0]).encode()).decode("ascii")


def _headers(token, body):
    h = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "Content-Length": str(len(body.encode())),
        "X-WECHAT-UIN": _uin(),
        "iLink-App-Id": ILINK_APP_ID,
        "iLink-App-ClientVersion": str(ILINK_APP_CLIENT_VERSION),
    }
    if token:
        h["Authorization"] = "Bearer " + token
    return h


def _jd(p):
    return json.dumps(p, ensure_ascii=False, separators=(",", ":"))


def discover_bots():
    """列出 accounts 目录里可用的 bot id（跳过 sync / context-tokens / 文件名污染的文件）。"""
    out = []
    for p in sorted(glob.glob(os.path.join(ACCOUNTS_DIR, "*.json"))):
        name = os.path.basename(p)
        if name.endswith(".sync.json") or name.endswith(".context-tokens.json"):
            continue
        if not name.endswith("@im.example.json"):
            print(f"[跳过] 文件名可疑（可能是写盘污染）: {name!r}")
            continue
        out.append(name[: -len(".json")])
    return out


async def probe(aid):
    cred_path = os.path.join(ACCOUNTS_DIR, f"{aid}.json")
    if not os.path.exists(cred_path):
        print(f"--- {aid}  ❌ 找不到凭证文件 {cred_path}")
        return
    cred = json.load(open(cred_path))
    token = cred.get("token")
    base = (cred.get("base_url") or ILINK_BASE_URL).rstrip("/")

    sync_path = os.path.join(ACCOUNTS_DIR, f"{aid}.sync.json")
    buf = ""
    if os.path.exists(sync_path):
        try:
            buf = json.load(open(sync_path)).get("get_updates_buf", "")
        except Exception:
            pass

    body = _jd({"get_updates_buf": buf, "base_info": {"channel_version": CHANNEL_VERSION}})
    try:
        import certifi

        conn = aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=certifi.where()))
    except Exception:
        conn = None

    import aiohttp

    async with aiohttp.ClientSession(trust_env=True, connector=conn) as s:
        async with s.post(
            f"{base}/ilink/bot/getupdates",
            data=body,
            headers=_headers(token, body),
            timeout=aiohttp.ClientTimeout(total=25),
        ) as r:
            raw = await r.text()
            out = f"/tmp/ilink_probe_{aid.split('@')[0]}.json"
            with open(out, "w") as fh:
                fh.write(raw)
            print(f"--- {aid}  uid={cred.get('user_id')}  saved_at={cred.get('saved_at')}")
            print(f"    HTTP {r.status}  raw saved -> {out}")
            try:
                j = json.loads(raw)
            except Exception:
                print(f"    ⚠️ 非 JSON 响应: {raw[:200]}")
                return
            ret, errcode, errmsg = j.get("ret"), j.get("errcode"), j.get("errmsg")
            msgs = j.get("msgs") or []
            if errcode == -14 or ret == -14:
                verdict = "❌ 会话已过期(session timeout) —— 只能重新扫码"
            elif ret == -2 or errcode == -2:
                verdict = "⚠️ stale-session/限流信号(ret=-2) —— 看 errmsg: 'unknown error'=stale, 'rate limited'=限流"
            elif ret in (0, None) and errcode in (0, None):
                verdict = "✅ 会话正常，凭证有效"
            else:
                verdict = "❓ 未知返回码"
            print(f"    ret={ret} errcode={errcode} errmsg={errmsg!r} msgs={len(msgs)}")
            print(f"    判定: {verdict}")
            for m in msgs[:10]:
                txt = ""
                for it in m.get("item_list") or []:
                    if it.get("type") == 1:
                        txt = (it.get("text_item") or {}).get("text", "")
                print(f"      from={str(m.get('from_user_id'))[:26]} at={m.get('create_time')} text={txt[:60]!r}")
            if msgs:
                print("    ⚠️ 有未收消息 —— 原始响应已落盘，不要重复拉取，先交给人看")


async def main():
    args = sys.argv[1:]
    if args:
        targets = args
    else:
        targets = discover_bots()
        if not targets:
            print(f"没找到任何 bot 凭证（{ACCOUNTS_DIR}）")
            return
        print(f"发现 {len(targets)} 个 bot: {', '.join(targets)}\n")
    for aid in targets:
        try:
            await probe(aid)
        except Exception as e:
            print(f"--- {aid}  异常: {type(e).__name__}: {e}")
        print()


if __name__ == "__main__":
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        sys.exit(
            "需要 aiohttp。用 hermes 自带 venv 跑：\n"
            "  ~/.hermes/hermes-agent/venv/bin/python " + os.path.abspath(__file__)
        )
    asyncio.run(main())
