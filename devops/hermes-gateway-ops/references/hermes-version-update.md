# Hermes 自身版本更新（升级 gateway 所在仓库）

目标：把 `~/.hermes/hermes-agent` 从旧版升到新版，**不丢用户设置、不留下半旧半新的运行态**。

## 顺序（照做）

```bash
cd ~/.hermes/hermes-agent

# 1. 先看落后多少
venv/bin/hermes update --check

# 2. 快照要保住的设置（迁移会重置它们，这是唯一对照表）
grep -nE "personality:|max_concurrent_children:|max_iterations:|archive_after_days:|stale_after_days:|_config_version:" ~/.hermes/config.yaml

# 3. 备份 + 写回滚脚本（先备份再更新，永不例外）
#    config/.env/profiles/skills/cron/memories/plugins + venv

# 4. 更新（后台跑，已手动备份才用 --no-backup）
venv/bin/hermes update --yes --no-backup   # 日志 ~/.hermes/logs/update-<日期>.log

# 5. 全新进程里补跑迁移，直到 _config_version 达到新代码要求的数字
venv/bin/hermes doctor --fix

# 6. 逐条恢复第 2 步快照里被冲掉的设置
venv/bin/hermes config set display.personality kawaii
venv/bin/hermes config set delegation.max_concurrent_children 3

# 7. 清更新过程留下的过期字节码
find ~/.hermes/hermes-agent -name '__pycache__' -type d -prune -exec rm -rf {} +

# 8. 让用户发 /restart（绝不自己按重启）

# 9. 复验
venv/bin/hermes --version        # upstream <sha> · local <sha> (+N carried commits)
systemctl show hermes-gateway -p ActiveState -p SubState -p ExecMainStartTimestamp
ps -eo pid,lstart,etimes,cmd | grep "hermes_cli.main gateway run" | grep -v grep
venv/bin/hermes doctor
venv/bin/hermes cron list
```

## 坑（都真实踩过）

1. **配置迁移只走到一半**：更新进程用的是**内存里的旧代码**，它只能把 config 迁到旧代码的天花板（例：v23→v37），而新代码要更高的版本（例：v44）。所以更新后必须在**新代码的进程**里再跑一次 `doctor --fix`；只跑一次会让 config 停在一个两边都不认的中间版本。
2. **每一轮迁移都会把用户设置重置成默认值**。实测被冲掉的是 `display.personality`、`delegation.max_concurrent_children`、`curator.archive_after_days` / `stale_after_days`。有几轮迁移就要恢复几轮——**别只查一次就宣布完成**。
3. **混态运行**：硬盘上是新代码、gateway 内存里是旧代码。症状是定时任务以 ImportError 失败，而报的符号**在文件里明明存在**（例：`cannot import name '_ensure_cron_dir' from 'cron.jobs'`），同时平台限流会把失败通知挡掉、用户什么都看不到。看到"函数存在却 import 不到"，先怀疑混态 + 过期 `__pycache__`，**不要去改代码**，走完第 7、8 步即可。
4. **判断用户到底重启没有**：拿进程启动时刻和更新日志 mtime 比。启动时刻**早于**更新结束 = 还在跑旧代码，此时所有"新功能为什么没生效"的疑问都有答案。`hermes --version` 只说明硬盘上的版本，不说明在跑的版本。
5. 官方更新自带优雅排水（等当前轮说完再重启），但仍需要一次 `/restart` 才能让 gateway / cron ticker / MCP 全部换成新代码。
6. `hermes update` 期间会出现内部瞬时 import 报错（如 `line_input`）——先别慌，在新进程里 import 一次验证即可。`hermes version` 不是子命令，取版本要用 `hermes --version`。
