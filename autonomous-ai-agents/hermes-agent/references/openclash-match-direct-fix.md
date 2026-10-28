# OpenClash MATCH,DIRECT 兜底规则修复

## 现象

用户 PC 通过 OpenClash 上网，国内网站（百度、抖音）间歇性超时，外网速度 20-40M（实际宽带 877Mbps）。Speedtest 直连测速正常，但通过 OpenClash 的国内直连下载只有几百 Byte/s。

## 根因

OpenClash 配置 `ddrdog.yaml` 的**最终兜底规则**被改为 `MATCH,DIRECT`，正确值应为 `MATCH,SSRDOG`（用户代理服务商组）。

```
- MATCH,DIRECT    ← 错误：所有未匹配规则走直连（包括外网流量）
- MATCH,SSRDOG    ← 正确：未匹配流量走 SSRDOG 代理组
```

影响范围：任何未匹配到规则集的流量（GitHub、Microsoft telemetry、各种 CDN 请求等）全部走直连。由于 OpenClash 的 Fake-IP 模式在直连时对境外 IP 无优化，速度极慢。

## 修复步骤

```bash
sshpass -p 'PASSWORD' ssh -p PORT root@ROUTER_IP "
  sed -i 's/MATCH,DIRECT/MATCH,SSRDOG/' /etc/openclash/config/ddrdog.yaml
  /etc/init.d/openclash restart
"
```

## 同时检查 custom_rules.list

`custom_rules.list` 中新增的规则（如 huggingface.co / brightdata.com 走 SSRDOG）语法正确但可能影响 OpenClash 的路由处理。建议保持最小化——只放 Tailscale 直连和 NAS 旁路规则，其他域名级代理走 `ChinaMax.yml` 规则集。

## 配置遗留

- **当前配置 ddrdog.yaml**：`/etc/openclash/config/ddrdog.yaml`
- **永久备份**：`/etc/openclash/config/ddrdog.yaml.bak.permanent`
- **custom_rules.list**：`/etc/openclash/custom/openclash_custom_rules.list`
- **重启命令**：`/etc/init.d/openclash restart`
- **运行日志**：`/tmp/openclash.log`
- **OpenClash 内核进程检查**：`ps | grep clash`

## 诊断要点

1. Speedtest 在路由器上正常（`speedtest -s 24447` 826Mbps）但 curl 国内站点慢 → 问题在 OpenClash 处理层
2. 关闭 OpenClash（`/etc/init.d/openclash stop`）后国内网站正常 → 确认 OpenClash 是瓶颈
3. 检查 `ddrdog.yaml` 最后一行 MATCH 规则 → 发现被改为 DIRECT
4. 对比永久备份（`MATCH,SSRDOG`）确认正确值

## 相关 skill

- `devops/router-ssh-security`：SSH 登录相关的安全防御
- `autonomous-ai-agents/hermes-agent`：Hermes 主技能，含 cron 和 iLink 相关信息
