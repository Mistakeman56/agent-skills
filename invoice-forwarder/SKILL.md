---
name: invoice-forwarder
description: "Monitor Agent Mail inbox for invoice emails, download PDF attachments, and forward to user via WeChat."
trigger: "when invoice email arrives at agent@example.com"
---

# Invoice Forwarder

## 功能
定期检查 Agent Mail (agent@example.com) 收件箱，发现发票邮件后自动下载 PDF 附件并通过微信发给assistant。

## 检查流程

```bash
# 1. 列出未读邮件（输出本身已是 JSON；v1.0.x 无 --json 标志）
agently-cli message +list --dir inbox --is-unread --limit 50

# 2. 读取邮件详情，提取 message_id / attachment_id / 正文中的附件直链
agently-cli message +read --id <message_id>

# 3a. 有附件时下载附件
cd ~/.hermes/office-docs/
agently-cli attachment +download --msg <message_id> --att <attachment_id> --output .

# 3b. 无附件但正文含 PDF 直链（京东数电发票）→ 从正文提取链接用 curl 下载，见 references/jd-digital-invoice.md

# 4. 标记已读：+read 会自动标记已读（无 --mark-read 标志），可用 +list --is-unread 验证
agently-cli message +read --id <message_id>
```

## 无未读邮件时的核查（避免漏发/重发）

**第一件事：查台账** `~/.hermes/office-docs/发票台账.json` —— 里面记录了每张发票的 `invoice_no` / `amount` / `file` / `sent_at`（实际交付给assistant的时间）。**台账里有 `sent_at` 的→已发过，绝不重发。**

```bash
python3 -c "
import json;d=json.load(open('~/.hermes/office-docs/发票台账.json'))
print([i['invoice_no'] for i in d['invoices'] if i.get('sent_at')])"
```

台账查不到时才走下面的老办法（历史遗留，仅用于 2026-09-11 之前的记录）：
1. `ls -la ~/.hermes/office-docs/` 看 PDF 是否已下载（mtime 即处理时间）
2. 直接查会话库（比 session_search 可靠，session_search 对这些内容常常返回空）：
   ```bash
   python3 -c "
   import sqlite3,re
   c=sqlite3.connect('~/.hermes/state.db')
   for r in c.execute(\"select content from messages where role='assistant' and content like '%MEDIA:%office-docs%'\"):
       print(re.findall(r'MEDIA:([^\s\)\]\n\`]+)', r[0]))"
   ```
   只有出现在 assistant 消息 `MEDIA:` 里的文件才算真正发出过（cron 投递机制同理）。
   - 已确认转发过 → `[SILENT]`，绝不重复发送
   - PDF 已下载但查不到 MEDIA 记录（漏发）→ 本轮补发并简要说明发票内容

**发完必须回写台账**（新增条目 + `sent_at`），否则下次又要从头考古。批量发多张时可以合并成一个 PDF（`pdfunite a.pdf b.pdf out.pdf`）再发，省得刷屏。

## 零 token 自动盯梢（推荐配置，2026-09-11 起启用）

用 **cron + `monitor_script`** 实现"盯着不花 token、有新信才唤醒 agent"：

- 脚本 `~/.hermes/scripts/invoice_monitor.py` 打印收件箱的**稳定快照**（message_id + created_at + from + subject + 是否有附件，**按 created_at 排序**）。
- 关键：**故意不输出 `is_read` / `snippet`** —— 我每读一封信 is_read 就翻转，会把"变化"报个没完。
- 查询失败时**回放上次成功快照**（缓存 `~/.hermes/state/invoice_monitor_last.txt`），否则网络抖一下就会误报变化唤醒 agent。
- 调度器逻辑：脚本输出**字节不变 → 完全跳过 LLM**（0 token，静默 tick）；输出变了 → 注入 MONITOR CHANGE DETECTED → 才跑 agent。
- 首次 tick 必定跑一次 agent（建基线），提示词里要写好"没有 MONITOR CHANGE DETECTED 就回 [SILENT]"。

**创建命令的坑**：
- `schedule='30m'` 会被解析成**一次性任务**（`repeat: once`），跑完就没了！
- 要循环必须写 **`schedule='every 30m'`**（或 cron 表达式 `*/30 * * * *`）。
- 且**事后 `update` schedule 不会重置 repeat**，只能删掉重建。
- 当前 job：`发票盯梢（收件箱）`，`every 30m`，`repeat: forever`，`monitor_script=invoice_monitor.py`，toolsets `[terminal, file]`，deliver=origin。

## 自动归档到 Stirling-PDF（2026-10-27 起启用）

发票除了发微信，还会自动上传到 Stirling-PDF 文件库的「发票」文件夹，长期留存可检索。

- **脚本**：`~/.hermes/scripts/invoice_archive.py`
- **调度**：`invoice-archive.timer`（systemd），每 30 分钟在 `:15` / `:45` 跑，与盯梢 cron 错开
- **源目录**：`~/.hermes/office-docs/*.pdf`，扫到就传，**纯脚本 0 token**
- **幂等**：已传文件记在 `~/.hermes/state/invoice_archived.json`，不会重复上传
- **凭据**：`.env` 的 `STIRLING_USER` / `STIRLING_PASSWORD`

**Stirling-PDF 部署**：PVE CT <ID>，`192.0.2.10:8080`，域名 `https://pdf.example.com:18443`。

**关键 API**（改脚本时照抄，别猜）：
```
POST /api/v1/auth/login                    {"username":..,"password":..} → session.access_token
POST /api/v1/storage/folders               {"name":"发票","parentFolderId":null} → id
POST /api/v1/storage/files                 multipart 字段名必须是 file（无 folderId 参数）→ id
PATCH /api/v1/storage/files/folder         {"fileIds":[..],"folderId":"<uuid>"} 批量移动；folderId 传 null 移出
```

**分类过滤**（`is_invoice()`）：文件名含「发票」/`invoice`、`digital_` 开头、或 ≥15 位数字发票号开头才算发票；笔记、流程图、汇报材料**不要**混进发票夹。

**日志**：`journalctl -u invoice-archive.service -n 30`

## 发送规则
- 下载 PDF 后用 `send_message` 发到微信：`MEDIA:~/.hermes/office-docs/<filename>`
- 如果邮件主题/正文含"发票""invoice""收据"等关键词，优先处理
- 每次检查间隔：30分钟
- 静默模式：没有新邮件时不打扰用户

## 注意事项
- 需要先完成 `agently-cli auth login` 授权
- 代理清除：必须 unset 全部代理变量 —— http_proxy https_proxy HTTP_PROXY HTTPS_PROXY **以及 ALL_PROXY CLASH_PROXY**（漏掉后者 curl/CLI 仍会尝试连 192.0.2.10:7890 而连接失败）
- 邮件来自发票系统（如拼多多、京东、淘宝等电商平台）
- 附件一般是 PDF 格式的电子发票；京东数电发票邮件**没有附件**，PDF/XML 直链在正文 HTML 里（见 references/jd-digital-invoice.md）
- 以 cron 方式运行时没有 send_message 工具：把 `MEDIA:~/.hermes/office-docs/<filename>` 直接写进最终回复，由 cron 投递机制转发给assistant
- 发送时在回复中简要说明发票内容（品名/金额/开票方/开票日期），可用 pdftotext 从 PDF 提取后描述
