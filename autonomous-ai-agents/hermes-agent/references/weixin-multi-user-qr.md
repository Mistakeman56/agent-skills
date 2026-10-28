# WeChat iLink Bot: Multi-User QR Code Quirk

## 关键发现

每个 `get_bot_qrcode` 调用生成一个**全新的 bot 实例**。网关只能连接到一个 bot 实例并轮询其消息。

扫描 QR 码后，用户的 WeChat 会绑定到该 bot。后续所有经此 bot 的消息都会被网关的 `get_updates` 轮询捕获。

## 多用户接入方案

### ❌ 错误做法
为每个新用户调用 `get_bot_qrcode`（不加参数）→ 每个用户绑定不同 bot → 网关只能收到一个用户的消息。

### ✅ 正确做法
1. 首用户通过普通 QR 码接入（创建 bot A）
2. 网关配置连接到 bot A
3. 后续用户需要加入**同一个 bot A**，而非创建新 bot
4. 调用 `get_bot_qrcode?bot_type=3&ilink_bot_id=<EXISTING_BOT_ID>` 生成指向现有 bot 的 QR 码
5. 新用户扫描该 QR → 绑定到 bot A → 网关可收到所有用户消息

## 识别不同用户
网关收到消息时，`from_user_id` 字段是不同的 WeChat ID。可以通过该字段区分不同用户。

## 凭证存储
每个 bot 的凭证保存在：
```
~/.hermes/weixin/accounts/<ilink_bot_id>.json
```
包含 `token`, `base_url`, `user_id`。

## 代码参考：gateway/platforms/weixin.py
- `EP_GET_BOT_QR = "ilink/bot/get_bot_qrcode"` — 生成 QR
- `EP_GET_QR_STATUS = "ilink/bot/get_qrcode_status"` — 轮询状态
- `_poll_loop()` — 通过 `get_updates` 获取所有绑定用户的消息
- `_process_message()` — 处理消息，不按 sender_id 过滤（仅过滤 bot 自身）
