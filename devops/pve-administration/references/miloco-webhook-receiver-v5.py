#!/usr/bin/env python3
"""
Miloco → Hermes 实时 Webhook 接收器 v5
接收 Miloco 感知事件推送，解析后通过对应楼层的小爱音箱主动说话 + 微信通知。
运行在 CT <ID> (192.0.2.10)，端口 18789。

关键设计：
1. 不同音箱型号的 play-text action IID 不同（蓝色 action.5.3，小米Pro action.7.3）
2. 按事件来源路由到对应楼层音箱
3. 智能过滤低价值事件（书房衣物、前院水渍等）
4. 通知冷却：相同内容 5 分钟内不重复
5. SSH 到 CT <ID> 必须通过 PVE 宿主机（pct exec）
"""
import json
import os
import time
import uuid
import subprocess
import re
import threading
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify

app = Flask(__name__)

QUEUE_DIR = Path("~/.hermes/miloco-events")
QUEUE_DIR.mkdir(parents=True, exist_ok=True)
RECENT_FILE = QUEUE_DIR / "recent.json"

# PVE/CT <ID> 配置
PVE_HOST = "192.0.2.10"
SSH_PASS = "<PASSWORD>"
CTID = 310
MILoco_CLI = "/usr/local/bin/miloco-cli"

# 音箱配置（每个音箱有不同的 action ID）
SPEAKERS = {
    "三楼书房": {"did": "979939218", "name": "蓝色智能音箱", "action": "action.5.3"},
    "客厅": {"did": "981192128", "name": "Xiaomi 智能音箱 Pro", "action": "action.7.3"},
    "二楼主卧": {"did": "979931026", "name": "橙色智能音箱", "action": "action.7.3"},
}

RUNS = {}
RUN_TTL = 300
NOTIFY_COOLDOWN = 300
LAST_NOTIFY = {}
PRIORITY_FORWARD = {"medium", "high", "urgent"}
IGNORE_KEYWORDS = ["书房沙发上堆满衣物", "前院地面有水渍", "地面有明显水渍"]

def get_speaker_for_source(source):
    if "三楼" in source or "书房" in source: return "三楼书房"
    elif "二楼" in source or "主卧" in source: return "二楼主卧"
    elif "客厅" in source: return "客厅"
    else: return "三楼书房"  # 默认

def speak_via_speaker(text, speaker_key):
    speaker = SPEAKERS.get(speaker_key)
    if not speaker: return False
    def _speak():
        try:
            safe_text = text.replace("'", "\\'")
            cmd = (f'sshpass -p "{SSH_PASS}" ssh -o StrictHostKeyChecking=no root@{PVE_HOST} '
                   f'"pct exec {CTID} -- {MILoco_CLI} device action {speaker["did"]} {speaker["action"]} '
                   f"'text-content:string={safe_text}'\"")
            subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        except Exception as e:
            print(f"[{datetime.now().isoformat()}] TTS异常: {e}")
    threading.Thread(target=_speak, daemon=True).start()

# ... (完整实现见 ~/.hermes/scripts/miloco-webhook-receiver.py)
