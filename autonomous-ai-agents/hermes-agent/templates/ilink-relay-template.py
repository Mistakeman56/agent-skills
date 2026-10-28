#!/usr/bin/env python3
"""
iLink Bot 双工中继模板（持久会话版）

使用方式：
  1. 修改 BOT_TOKEN / ACCOUNT_ID / USER_ID 为实际值
  2. python3 this_script.py              # 启动轮询（收发一体）
  3. echo '{"text":"消息内容"}' >> queue  # 写入发送队列

架构：
  单个 aiohttp.ClientSession 同时处理 getupdates（收）和 sendmessage（发）
  发送队列文件由外部进程（cron job 等）写入，轮询循环自动消费
"""

import asyncio, aiohttp, json, os, time, logging, secrets, struct, base64, uuid

# ── 配置区（修改为实际值）──
BOT_TOKEN = "your_bot_token@im.example:hex..."
ACCOUNT_ID = "your_account_id@im.example"
USER_ID = "target_user_id@im.example"    # 目标用户微信ID
MSG_FILE = "/tmp/messages.jsonl"         # 收到的消息
SEND_QUEUE = "/tmp/send_queue.jsonl"     # 发送队列文件
SEND_LOG = "/tmp/send_done.jsonl"       # 发送记录
LOG_FILE = "/tmp/ilink_relay.log"
# ── 配置结束 ──

ILINK_BASE_URL = "https://ilinkai.weixin.qq.com"
ILINK_APP_ID = "bot"
CHANNEL_VERSION = "2.2.0"

logging.basicConfig(level=logging.INFO,
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
logger = logging.getLogger("ilink_relay")
MOM_TOKEN, MOM_BASE_URL = BOT_TOKEN, ILINK_BASE_URL

def _uin():
    return base64.b64encode(str(struct.unpack(">I", secrets.token_bytes(4))[0]).encode()).decode()

def _base_info(): return {"channel_version": CHANNEL_VERSION}
def _jd(p): return json.dumps(p, ensure_ascii=False, separators=(",", ":"))

def _headers(token, body):
    h = {"Content-Type":"application/json","AuthorizationType":"ilink_bot_token",
         "Content-Length":str(len(body.encode())),"X-WECHAT-UIN":_uin(),
         "iLink-App-Id":ILINK_APP_ID,
         "iLink-App-ClientVersion":str((2 << 16) | (2 << 8) | 0)}
    if token: h["Authorization"] = f"Bearer {token}"
    return h

async def _api_post(session, endpoint, payload, timeout_ms):
    body = _jd({**payload, "base_info": _base_info()})
    url = f"{MOM_BASE_URL.rstrip('/')}/{endpoint}"
    async with session.post(url, data=body, headers=_headers(MOM_TOKEN, body),
            timeout=aiohttp.ClientTimeout(total=timeout_ms/1000)) as r:
        raw = await r.text()
        if not r.ok: raise RuntimeError(f"HTTP {r.status}: {raw[:200]}")
        return json.loads(raw)

async def send_message(session, text, ctx_token=None):
    client_id = f"ilink-relay-{uuid.uuid4().hex}"
    msg = {"from_user_id":"","to_user_id":USER_ID,"client_id":client_id,
           "message_type":2,"message_state":2,
           "item_list":[{"type":1,"text_item":{"text":text}}]}
    if ctx_token: msg["context_token"] = ctx_token
    resp = await _api_post(session, "ilink/bot/sendmessage", {"msg": msg}, 15000)
    ret = resp.get("ret", 0)
    if ret not in (0, None):
        if (ret in (-14, -2) or resp.get("errcode") in (-14, -2)) and ctx_token:
            logger.info("会话过期重试")
            del msg["context_token"]
            r2 = await _api_post(session, "ilink/bot/sendmessage", {"msg": msg}, 15000)
            return r2.get("ret", -1) in (0, None)
        return False
    return True

async def process_queue(session):
    if not os.path.exists(SEND_QUEUE): return
    try:
        with open(SEND_QUEUE) as f: lines = f.readlines()
        open(SEND_QUEUE, "w").close()
    except: return
    for line in lines:
        line = line.strip()
        if not line: continue
        try:
            e = json.loads(line)
            ok = await send_message(session, e["text"], e.get("ctx"))
            with open(SEND_LOG, "a") as f:
                f.write(json.dumps({"ts":time.time(),"text":e["text"][:100],
                    "success":ok}, ensure_ascii=False)+"\n")
            logger.info(f"{'✅' if ok else '❌'} 发送: {e['text'][:50]}")
        except Exception as ex: logger.error(f"队列: {ex}")

async def poll():
    sync_buf = ""
    sf = f"~/.hermes/weixin/accounts/{ACCOUNT_ID}.sync.json"
    try:
        if os.path.exists(sf): sync_buf = json.load(open(sf)).get("get_updates_buf","")
    except: pass
    try:
        import ssl, certifi
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=certifi.where()))
    except: connector = None

    logger.info("启动轮询（持久会话）")
    async with aiohttp.ClientSession(trust_env=True, connector=connector) as session:
        last_qc = 0
        while True:
            try:
                resp = await _api_post(session, "ilink/bot/getupdates",
                    {"get_updates_buf": sync_buf}, 35000)
            except asyncio.TimeoutError: continue
            except Exception as e:
                logger.error(f"轮询: {e}"); await asyncio.sleep(5); continue
            ret = resp.get("ret", 0)
            if ret not in (0, None) and ret != -14: await asyncio.sleep(2); continue
            if ret == -14: logger.warning("过期"); await asyncio.sleep(10); continue
            nb = str(resp.get("get_updates_buf",""))
            if nb: sync_buf = nb
            try: json.dump({"get_updates_buf": sync_buf}, open(sf,"w"))
            except: pass
            for msg in resp.get("msgs") or []:
                sid = str(msg.get("from_user_id",""))
                if not sid or sid == ACCOUNT_ID: continue
                text = ""; ctx = ""
                for it in msg.get("item_list") or []:
                    if it.get("type")==1: text = str(it.get("text_item",{}).get("text",""))
                ctx = str(msg.get("context_token") or "").strip()
                with open(MSG_FILE,"a") as f:
                    f.write(json.dumps({"ts":time.time(),"from":sid,"text":text,
                        "ctx":ctx}, ensure_ascii=False)+"\n")
                logger.info(f"📩 {text}")
            if time.monotonic() - last_qc >= 5:
                await process_queue(session); last_qc = time.monotonic()

if __name__ == "__main__":
    try: asyncio.run(poll())
    except KeyboardInterrupt: logger.info("已停止")
