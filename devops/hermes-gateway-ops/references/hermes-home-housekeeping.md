# `~/.hermes` 磁盘清理与残留退役（housekeeping）

适用：`~/.hermes` 体积失控（实测曾 4.9 GB）、某个自建中继/脚本退役后留下垃圾、日志刷屏、凭证目录里有死号。
配套：`references/weixin-session-expiry.md`（微信凭证排查）。

## 0. 铁律：先打包，再删（可回滚）

**任何删除都先归档再删**，一步 tar + 一步 rm，全程可回滚：

```python
import tarfile, os
H = "~/.hermes"; ARCH = f"{H}/archive/cleanup-<name>-<stamp>.tar.gz"
os.makedirs(os.path.dirname(ARCH), exist_ok=True)
with tarfile.open(ARCH, "w:gz") as tf:
    for p in targets:                      # 绝对路径列表
        tf.add(p, arcname=os.path.relpath(p, H))
for p in targets: os.remove(p)
```

实测 604 KB 的残留 → 存档只有 54 KB（压缩比高，留着不心疼）。**别问用户"要不要备份"**，直接打包，报告里说一句存档路径即可。

## 1. 动手前：确认没有活引用（有个大陷阱）

```bash
grep -rl "<脚本名>\|<db名>" ~/.hermes/ --include='*.yaml' --include='*.json' --include='*.service' 2>/dev/null
grep -rl "<脚本名>" /etc/systemd/system/ /etc/cron* 2>/dev/null
```

⚠️ **陷阱**：`~/.hermes/sessions/*.json`（历史会话转录）和技能里的 `references/*.json` **一定会命中**，
它们只是"当年聊过这个文件"的历史记录，**不是活引用**。判读时先排除 `sessions/`，再用 `ps` 与 `crontab -l` 确认没有进程/定时任务在跑。

## 2. 什么可以放心清（本机实测）

| 目标 | 实测规模 | 说明 |
|---|---|---|
| `logs/mcp-stderr.log` | **27 MB** | MCP stdio 噪音，内容基本是 `Processing request of type PingRequest`。**截断即可**（`: > file`），无需删；进程按 O_APPEND 写不会被打断 |
| `logs/*.log.1` `.2` `.3` | ~24 MB | 轮转归档。**保留当前 `agent.log` / `gateway.log` / `errors.log`**，只删带序号后缀的 |
| `state-snapshots/<ts>-pre-update/` | **523 MB** | 升级前一次性状态快照。升级已成过去式就是死重，可删（**先问**：它是 state.db 唯一的恢复点） |
| `sessions/*.json` | **1.4 GB**（9,738 个） | 历史会话转录。删 N 天前的可省 ~1 GB，但**先问**（可能想 `/resume`） |
| 过期配置备份 | 各 ~9–14 KB | `config.yaml.bak` / `.deepseek.bak` / `.moonshot.bak`。**只留最近一个回滚点**（命名带日期的那个） |
| 死凭证 / 乱码文件名文件 | 几百 B | 见 §3 |
| 空诊断日志 | 0 B | `logs/*diag*.log` 且 size==0 |

**不要碰**：`bin/`、`profiles/`、`models_dev_cache.json`、正在跑的网关 + 其当前日志、
以及 **`state.db`**（1 GB，7 万条消息）—— 它被网关持有锁，**VACUUM 需要独占锁，运行期做不了**，不要试图在网关活着时压缩。

## 3. 清理平台凭证目录（`weixin/accounts/`）

```python
import os
d = "~/.hermes/weixin/accounts"
for n in sorted(os.listdir(d)):
    bad = any(ord(c) < 32 for c in n)          # 乱码/含控制字符的文件名
    print(repr(n), os.path.getsize(os.path.join(d, n)), "⚠️" if bad else "")
```

判读规则：

- **死号可删**：探活返回 `errcode=-14 session timeout` 的 bot json（见同目录 skill 的 `scripts/ilink_bot_probe.py`）。
- **活号绝不可删**：探活 `ret=None errcode=None` 的凭证 —— 它代表"绑了几个月仍有效、以后接线不用重新扫码"。
- **乱码文件名的 json**（含 `\n\x11` 等控制字符）= 损坏的历史凭证，删。
- 顺手清 `.a271ec…sync_*.tmp` 这类中断留下的临时文件（同步游标文件 `*.sync.json` **属于活号的一部分，保留**）。

⚠️ 文件名含控制字符时，**不要用 shell glob/引号拼命令**（会被当成 URL 污染或参数拆分），用 Python 的 `os.listdir` 取 `repr` 精确匹配后再 `os.remove`。

## 4. 收尾核验（每次都要做）

```bash
ls -la ~/.hermes/mom_* 2>&1 | head -3          # 目标应已消失
ls -laS ~/.hermes/logs/ | head -8              # 只留当前日志
du -sh ~/.hermes                               # 前后体积对比
systemctl is-active hermes-gateway                 # 必须仍为 active（证明没碰活的东西）
ps -eo pid,etime,args | grep -iE '<被删脚本名>' | grep -v grep || echo "✅ 无残留进程"
```

## 5. 报告格式（用户偏好）

给一张表：**已清（分类 + 体积）/ 特意保留（含理由）/ 存档路径 / 剩下来需要用户点头的大块**。
用户讨厌反复确认小事，所以：**小的直接清 + 报告**，**大到丢数据的（历史、备份）列出来让他一句话决定**。
