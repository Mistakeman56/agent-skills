---
name: openclash-user-guide
description: 'Use when 排查/配置 OpenClash 或 Mihomo — 按路由表读子文档，先调试日志。'
---

# OpenClash 功能参考指南（入口）

> 来源：`vernesong/OpenClash` 仓库 `.github/skills/openclash-user-guide/`（dev 分支，MIT）。本地镜像：本技能 `references/` 目录下 18 份子文档 `NN-xxx.md`。
> **回答前先查下方「文档路由表」，用 `skill_view(name='openclash-user-guide', file_path='references/NN-xxx.md')` 只读命中那 1–2 份，禁止一次全读。**

## AI 行为总则

**排查优先级（逐层递进）**：
① **先要日志** — 用户报问题先生成调试日志（LuCI「运行日志 → 调试日志 → 生成日志」，或 SSH `/usr/share/openclash/openclash_debug.sh` → `/tmp/openclash_debug.log`，含依赖/配置/防火墙等 30 章节）
② **日志不足给命令** — 对照 `14-diagnostics.md` §14.2 决策树给精确 CLI（🟢安全查询优先，🟡/🔴附风险说明）
③ **定根因后给路径/模块** — LuCI 操作路径，或带段头的覆写模块（格式铁律见 `16-overwrite-module-format.md` §16.1）
④ **仍未解决查外部** — Issues（插件侧 OpenClash / 内核侧 Mihomo）/ 源码 / Mihomo Wiki
⑤ **AI 自助修复**（用户授权凭据后）：调试日志 → SSH 诊断 → 生成覆写模块写入路由器 `enable=0`，启用权留给用户（`14-diagnostics.md` §14.5–14.7）

| 原则 | 说明 |
|------|------|
| 需求模糊先澄清 | 缺功能/模式/预期/已试步骤 → 先短问，禁猜测作答 |
| 主动查证不猜测 | 本文档未覆盖的字段 → 查 Mihomo Wiki / Meta-Docs / 源码，禁止编造 |
| 查源码不只查文档 | 「为什么选项不生效」→ 必须读 OpenClash 源码 / Mihomo 源码里实际执行逻辑 |
| 配置给路径 | 功能开关 → LuCI 路径（如 服务 → OpenClash → 插件设置 → 流量控制），用户要 CLI 才给命令 |
| 解释原理 | 给步骤同时讲防火墙链/YAML 变换原理，降误操作风险 |
| 引用来源 | 外部查证的信息末尾注明来源；本文档信息注明章节号（如 `14-diagnostics.md` §14.2） |

**核心资源**：Mihomo Wiki `https://wiki.metacubex.one/config/`｜Meta-Docs `https://github.com/MetaCubeX/Meta-Docs`｜OpenClash Issues `https://github.com/vernesong/OpenClash/issues`｜Mihomo Issues `https://github.com/MetaCubeX/mihomo/issues`｜OpenClash 源码 `https://github.com/vernesong/OpenClash/tree/dev`｜Mihomo 源码 `https://github.com/MetaCubeX/mihomo/tree/Alpha`｜Smart 核心 `https://github.com/vernesong/mihomo/tree/Alpha`｜meta-rules-dat（master=构建脚本，meta=.mrs 编译产物，写 GEOSITE/GEOIP 前先看分类名）

## 文档路由表

| 用户问题类型 | 子文档（references/ 下） | 关键小节 |
|------|------|------|
| 整体原理 / 启动流程 | `01-architecture.md` | 分层架构、UCI 配置根、开机链路、热生效 vs 重启 |
| 启动失败 / 依赖缺失 | `02-dependencies.md` | 依赖清单、启动前检查、失败速查表 |
| 用户报错 / 日志异常 | `03-errors.md` | §3.1–3.16 错误关键字定位 |
| 透明代理 / 防火墙链 | `04-firewall-chains.md` | §4.1 模式×防火墙对照、§4.2 fw4 链结构（nft+iptables 双后端） |
| ICMP/Ping / 高级流量控制 | `05-firewall-special.md` | §5.1 ICMP 转发、§5.2 iptables 高级流量控制 |
| 选项→规则映射 / DNS 劫持 / 域名解析不到 | `06-firewall-options-dnsmasq.md` | §6.1 fw3 等效链、§6.2 选项影响、§6.3 dnsmasq 改写、§6.4 重绑定保护 |
| 运行状态页开关 | `07-page-overview.md` | §7.1–7.12 运行状态页/仪表盘/IP 检测 |
| 插件设置·模式/流量 | `08-settings-mode-traffic.md` | §8.2 运行模式（四栈/转发/TUN 参数）、§8.3 流量控制、§8.4 性能实测 |
| 插件设置·DNS/黑白名单/流媒体/IPv6 | `09-settings-dns-ac-ipv6.md` | §9.1 DNS、§9.2 黑白名单、§9.5 IPv6 |
| 插件设置·GEO/杂项/来源流量 | `10-settings-geo-misc-src.md` | §10.1 GEO 更新、§10.3 来源流量 |
| 覆写设置页(CBI) | `11-overwrite-settings.md` | §11.2 常规、§11.3 DNS、§11.4 Meta、§11.5 Smart、§11.6 规则、§11.7 认证 |
| 订阅 / 配置管理 | `12-subscribe-config.md` | §12.1–12.3 订阅、§12.4–12.8 配置切换 |
| 运行日志 / 调试日志 | `13-logs.md` | §13.2 三个标签页、§13.5 调试日志 30 章节 |
| CLI 诊断 / AI 自助修复 | `14-diagnostics.md` | §14.2 决策树、§14.3 命令、§14.4 脚本、§14.5–14.7 AI 流程 |
| LuCI / Mihomo HTTP API | `15-api.md` | §15.1 LuCI API、§15.2 内核 API |
| 覆写模块格式/操作符 | `16-overwrite-module-format.md` | §16.1 是什么、§16.2 格式铁律 |
| 覆写模块示例 / UCI 结构 | `17-overwrite-module-examples.md` | §17.3 示例、§17.5 UCI 结构 |
| 本文档未覆盖 | `99-out-of-scope.md` | 外部资源优先级与查询流程 |

## 本机（Hermes）补充纪律

- 路由器：`ssh -p2222 root@192.0.2.10 'sh -s'` stdin 脚本（busybox sh，**无 timeout 命令**，长任务用 `cmd & TP=$!; sleep N; kill $TP`）；`scp -P 2222`。
- **NEVER 手动 nohup 启动 mihomo**（看门狗双进程→断网）；只用 `/etc/init.d/openclash {start|restart|stop}`。
- 恢复/停止服务属状态变更，先问用户；纯诊断（日志、查询命令）直接做。
- **本机踩坑存档（2026-10-21 hdfans 直连修复）**：① 自定义规则实体 = `/etc/openclash/custom/openclash_custom_rules.list`（YAML，条目须 4 空格缩进；`custom_rules.list` 不是它读的路径）；fake-ip 过滤实体 = 同目录 `openclash_custom_fake_filter.list`（`+.域名`）。② 直接把规则写进 `/etc/openclash/config/9.1.yaml` 的 `rules:` 段也可（同样 4 空格缩进，写 2 空格会炸 YAML→mihomo 起不来；改完用 `/etc/openclash/clash -t -d /etc/openclash -f <cfg>` 验证）。③ 重启后 mihomo 消失+日志报 `OpenClash Now Disabled, Need Start From Luci Page` → `uci set openclash.config.enable='1'; uci commit openclash; /etc/init.d/openclash start`。④ 日志在 `/tmp/openclash.log`、`/tmp/openclash_start.log`。⑤ 验证规则生效：`curl -H 'Authorization: Bearer <secret>' http://127.0.0.1:9090/connections` 看 `chains`/`rule` 字段。⑥ PT 站「连接性为否」排查序：conntrack 看 51413 外部源 → `ifstatus wan` uptime 判重拨换 IP → 浏览器流量是否走了代理出口（fake-ip+全代理下站点看到的是节点 IP）→ 修法：站域名 DIRECT + fake_filter 白名单。⑦ 域名流量归因监控：本机 systemd 服务 `oc-traffic-monitor`（`/root/oc-traffic-monitor/`，10 秒轮询 mihomo `/connections` 落 sqlite `traffic.sqlite3` 留 180 天）；报表 `python3 report.py --days 7 [--link proxy|direct|all] [--host xx]`，含「⚠️疑似可直连」标记（国内关键词走了 PROXY 才标）；密钥在同目录 `.env`(600)。mihomo API 局域网可直连：`http://192.0.2.10:9090`。
