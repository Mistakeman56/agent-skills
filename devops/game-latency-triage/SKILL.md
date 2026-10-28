---
name: game-latency-triage
description: 'Use when 游戏不跟手/手感延迟高但游戏内 ping 与帧率都正常——分层定性，路由器侧常驻采样。'
---

# 游戏延迟 / 不跟手排查（分层定性法）

场景：用户说「明显有延迟、不跟手，但游戏里 ping 显示正常、帧率也没掉」。
这类症状的默认嫌疑是**输入/合成链路**，不是带宽也不是节点。**逐层拿证据排除，先别改任何配置**；
一上来调 QoS、换节点、改防火墙是浪费对局时间（用户往往正打着就来回话）。

## 分层定性（按序，每层给一条硬证据）

### 层1 代理层：游戏流量是否被卷入
- mihomo 侧归因：`curl -s -H "Authorization: Bearer <secret>" http://127.0.0.1:9090/connections`，
  按进程/域名筛游戏相关连接，看链是 `DIRECT` 还是节点。
- 国服游戏域名基本都被 `DOMAIN-SUFFIX,qq.com,DIRECT` 之类的规则放行；LOL 全链路（`*.lol.qq.com`、
  `wegame.com.cn`、`anticheatexpert.com` 反作弊）都应是直连。
- UDP 是否进代理：`uci get openclash.config.enable_udp_proxy`（`0` = 没加载任何 UDP TPROXY/REDIRECT，
  nft 里 UDP 只做 DNS 劫持 + 境外 443 QUIC REJECT）。对局内流量走 UDP，此项为 0 就已排除「对局被代理」。
- 判据组合：TCP 侧 DIRECT + UDP 侧未接管 = 代理层排除，往下走。

### 层2 路由器排队 / 整形
- `tc -s qdisc show dev pppoe-wan`：看 `pk_delay`/`av_delay`/`backlog`。
- **`pk_delay` 几百 µs 级且 `backlog 0b` = 没有排队**，SQM cake 的 `bandwidth 90Mbit` 只是整形上限，
  不代表拥塞。持续 `backlog > 0` 或 `pk_delay > 5ms` 才是排队问题。
- 同时抓 `conntrack` 确认对局 UDP 五元组确实经过这台路由（`grep src=<PC_IP> /proc/net/nf_conntrack | grep udp`），
  顺手把 `[UNREPLIED]` 和 8000/8081 端口区分开（8000 是对局，8081/语音/日志多为辅助）。

### 层3 端到端 RTT / 丢包（这一层要"在对局中"做）
- 三层对照 ping：PC→网关（内网应 <1ms）、PC→游戏服（国服 15~25ms 正常）、PC→PPPoE 对端（1~2ms）。
- **必须从 PC 上测一次**，不能只测路由器：用户感知的是 PC 的路径，PC 侧数据才是能拿给他看的硬证据。
- PC 侧快速抖动测量（20 秒出结果，对局中也敢跑）：`Test-Connection -Delay` 最小只接受 1 秒，
  要 0.15s 级采样就用 .NET 原生 Ping 循环（见 `references/win-latency-probes.md`）。
- Windows `ping -n 100`／`-n 200 -w 100` 经 ssh+iconv 管道常整条命令挂到 300s 超时；别用它测高密度采样，用上面的 .NET 循环。
- 路由器侧并行测多目标：`scripts/lat_jitter_check.sh <ip...>`（busybox，输出每个目标的丢包/最小-平均-最大/相邻抖动）。
- **判据**：两处都 0 丢包、抖动 <1ms（PC→游戏服 0.2~0.3ms 是实测常态）= 网络层彻底洗清，
  明确告诉用户"不是网络"，转层4；不要再在 QoS/节点上打转。

### 层4 客户端输入 / 合成链路（网络排除后才有意义）
- **网卡节能四件套**（Realtek 等家用网卡默认全开）：`*EEE`、`EnableGreenEthernet`、`GigaLite`、
  `*InterruptModeration` → 关掉。改前必须 `Export-Csv` 备份，改后 `Restart-NetAdapter`（断网约 10s），
  再读回四项确认。命令模板见 `references/windows-nic-tuning.md`。
- **虚拟显示器 / 串流常驻**：`Get-CimInstance Win32_VideoController` 里除独显外多出来的
  「虚拟显示适配器」（GameViewer/向日葵、ToDesk、Parsec 等）意味着合成器多绕一层；服务 Automatic 常驻，
  平时不远程时也应退出做 A/B。用 `Get-NetTCPConnection -OwningProcess` 判断是否有活跃串流会话
  （只有一条到厂商 443 的信令连接 = 没人在串流，但虚拟显示器仍挂着）。
- **无线鼠标**：多个 2.4G 接收器同时在线、电量低、干扰——手感与网络延迟几乎无法区分，做 A/B 很快。
- **游戏内设置**：垂直同步关、NVIDIA Reflex 开（或「开+增强」）、帧率上限 ≥ 显示器刷新率、
  独占全屏 + 关掉 Windows 全屏优化。这些远程查不到注册表项时直接让用户看一眼，别硬查。
- 系统侧：电源计划应为「高性能」，读一下 GPU 的 pstate/温度排除降频。
- **一次只改一类设置**：网卡四项 + 游戏内同步 + 退串流一起改，手感变化就归不了因。
  每改一批就立刻问用户「这局比上一局手感有变化吗」——他的体感是唯一判据，也决定下一步是保留还是回滚。

## 常驻采样（对局中才有数据）

症状只在打的时候出现，所以**必须先落一个路由器侧常驻采样**，再让用户开一局，回来读日志定案。

- 脚本：`scripts/pppoe_latency_mon.sh`（busybox 兼容，参数化 PC IP；每 5s 采 cake 延迟/backlog、
  pppoe tx_bytes、网关与游戏服 RTT、PC 游戏 UDP 五元组；日志超 2MB 自动截断）。
- 部署：heredoc 灌到路由器 `/root/`，然后写 `/etc/crontabs/root` 一行 `* * * * * /root/<脚本>`；
  脚本自带 pidfile + `kill -0` 幂等，被 cron 每分钟拉起也不会重复跑，进程崩了/重启后自愈。
- 装完必须验证：`ps w | grep <脚本>` 只有一个实例，且 `/tmp/*.log` 已有真实行（含 `pk_delay` 与五元组）。

## 坑（都会让「活」凭空消失）

- **Hermes 的 terminal 会直接拒掉前台命令里的 `nohup`/`setsid`/`&`**（报 shell-level backgrounding）。
  不要花时间绕过——常驻采集的正确形态是「目标机 cron + 幂等 pidfile」，不是本机 nohup。
- **`terminal(background=true)` 跑的 `ssh 路由器 sh /root/xx.sh` 会随 Hermes 会话结束一起死**：
  用户下次进来看到的是「刚才让你干的活没了」。凡是需要跨会话存活的，一律落到目标机 cron；
  遇到这种情况先走 interrupted-work-resume 把断点接回来，别从头重做。
- **OpenWrt 上已经有一个 `busybox crond -f -S`（s6 托管）**。再执行 `/etc/init.d/cron restart` 或 `enable`
  会起第二个 `/usr/sbin/crond -f -c /etc/crontabs` → **所有 cron 任务（netmon/devmon 等）跑两遍**，
  并留下 `/etc/rc.d/S??cron` 开机自启。建 cron 前先 `ps w | grep crond` 数实例；误开了就 kill 掉 +
  `rm /etc/rc.d/S??cron` 恢复原状（用户对「悄悄跑两遍」很敏感）。
- 路由器原厂 shell 无 `base64`，脚本只能 heredoc 灌（`ssh ... 'sh -s' <<'EOF'`），灌完 `chmod +x` 再验 `ls -l`。
- **busybox `ping` 的 `-i` 只收整数秒**：`ping -i 0.2` 直接报 `ping: invalid number '0.2'`，什么都不输出，
  看起来像"服务器不回包"。高密度采样靠「多目标并行 + `-i 1` + 多包」，不是靠缩短间隔。
- **解析 conntrack 必须按原始方向取字段**：每行后半段是回程元组，也带 `dst=`，naive 地取最后一个 `dst=`
  会拿到本机公网 IP（如 113.226.x）而不是游戏服。锚定原始方向（或只取每行第一次出现的 `src=<LAN_IP>` 之后那个 `dst`），
  否则后面 ping 的全是错目标。
- 别顺手改防火墙/nft 排除延迟：用户红线是「路由器防火墙严禁改动」，这类问题也不需要动它。

## 汇报纪律

- 第一次回复就给结论结构：**哪几层已排除（附证据）+ 还剩下的嫌疑 + 下一步 A/B 怎么做**，不要罗列命令过程。
- 一句话能说清的先说结论（如「LOL 没走代理、队列没排队，问题不在网络层」），再给数据。
- 排障期间收萌、直接给命令与结论；结论未定时**明确写「嫌疑」而不是定论**，别把猜测讲成已定案。
- **用户的「网速慢」和「不跟手」是两件事，分开定性再合并汇报**：延迟层已经洗清（0 丢包、抖动 <1ms）时，
  要明说「这条跟手感无关」；否则用户会把同一通电话里的「测速只有 5MB/s」当成不跟手的原因，
  情绪一路带到「我要重装软路由」。吞吐异常另走 speedtest-triage（含层4 出口限速定性）。

## 参考

- `scripts/pppoe_latency_mon.sh` — 路由器侧采样脚本（幂等，cron 保活）。
- `scripts/lat_jitter_check.sh` — 并行抖动/丢包取证（路由器直跑，多目标 40 包出一张表）。
- `references/windows-nic-tuning.md` — 网卡节能四项关闭 + 备份/回滚 + 只读体检命令。
- `references/win-latency-probes.md` — PC 侧 .NET Ping 循环 / 显卡-显示器-串流体检命令。
- 游戏**卡住/冻结/黑屏/失去响应**（渲染层死循环，不是延迟）不走本技能 → `game-hang-triage`。
