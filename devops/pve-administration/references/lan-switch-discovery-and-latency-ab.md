# 内网某一跳的定位：交换机后台发现 + 延迟归因

用户报「中间就差一台交换机，它后面的东西却更慢更抖」时，先用测量把责任落到具体一跳，再谈改配置。

## 一、归因：从软路由做 A/B ping（30 秒出结论）

1. 挑两个目标：**直连软路由的设备**（对照）与**挂在待测交换机后的设备**（实验组，NAS/AP 通常属于后者）。
2. 各打 40 包：`ping -c 40 -q <ip>`，读 `min/avg/max`（有 mdev 一起读）。
3. 判读：
   - 过交换机 ≈ 直连（都 < 0.5ms）→ **这一跳无罪**，停止怀疑网线/端口/交换机；
   - 明显更差 → 才进第二节查端口计数。
4. 汇报时给**两行对照数据**，只说「交换机是清白的」没有说服力。

**测速仪的延迟/抖动先归因再解释**：用户常在**容器里的浏览器**（NAS 或路由器上的 Firefox、测速网站）量内网 —— 那条路径多了 bridge NAT + 浏览器的 TLS/JS/渲染开销，抖动还会被 JS 定时器粒度（≈16–20ms）放大成一个恒定值，与上面的 A/B ping 不是同一条路。测速页报 7ms/20.45ms 而 A/B ping 两边都 0.3ms → 问题在测速路径或测速服务器，不在链路；**上行恰好 ≈1G** 时先怀疑测速服务器上行。要干净的内网吞吐/抖动用 **iPerf3**（一台 `iperf3 -s`、另一台 `iperf3 -c <ip>`），别用浏览器测。同类陷阱见 `home-network-outage-forensics.md` 的「测量陷阱」表。

## 二、端口与计数（只读；任何改动先备份 + 征得同意）

```sh
ethtool <if>                      # Speed/Duplex/Link —— 先确认看的是那条 2.5G
ethtool --show-eee <if>           # 经典抖动源是开着 EEE；disabled 即排除该嫌疑
ethtool -a <if>                   # pause RX/TX 是否 on；高速口靠它防打爆对端缓冲
ethtool -g <if>                   # Current vs Pre-set maximum（如 256 vs 4096）→ 缓冲余量
ethtool -S <if> | grep -v ': 0'   # rx_fifo_errors / rx_queue_*_drops / crc
```

- **丢包看速率不看总数**：隔 10 秒两次快照求差；delta=0 说明是历史累计，不是当前故障。
- 有 CRC/dup 无 fifo → 查线缆；只有 fifo/drops → 缓冲不足，候选动作是调大 RX ring（`ethtool -G`，属改动）。
- 找出哪个物理口接着那台交换机：
  ```sh
  ip -o link show | awk '$0 ~ /master br-lan/ {print $2}'    # br-lan 成员口
  bridge fdb show br br-lan | awk '/dev eth/{print $NF}' | sort | uniq -c | sort -rn   # MAC 数最多者
  ```
  `brctl show` 在 iStoreOS 上只回显 docker 桥，别拿它看 LAN 成员口。

## 三、发现一台「不在本网段」的网管交换机后台

网管交换机出厂网段通常与家里 LAN 不同 → **扫本网段找不到它，DHCP 租约里也不会有它**（别据此判定「它没有后台」）。两步解决：

1. 软路由与交换机 L2 直连，临时挂别名即可够到它（不拔线、不动 PC）：
   ```sh
   ssh -p 2222 root@192.0.2.10
   ip addr add 192.0.2.10/24 dev br-lan
   ping -c 2 192.0.2.10 && curl -s -m 5 http://192.0.2.10/   # 期望跳 /login.html
   ip addr del 192.0.2.10/24 dev br-lan                          # 探完即删
   ```
2. 品牌默认值（兮克轻管理型 SKS3200M 一类）：管理 IP `192.0.2.10`、`admin/admin`，根路径 JS 跳 `/login.html`。型号不同默认段可能不同（有的是 `192.0.2.X`），先查产品页再试。
3. **登录属凭证操作**：先 `browser_vault_list`；库里没有就 `browser_vault_save_login` 让用户在自己的 UI 里填，不要在对话里敲密码。若 `browser_vault_save_login` 返回 `prompt_unavailable`（headless/cron/API 会话弹不出窗），让用户自己 `hermes vault add` 或走 桌面端 → 设置 → 密码与登录 存该 origin，存好再 `browser_vault_fill`。
4. 进去后第一件事：把管理 IP 改到 LAN 网段（或开 DHCP 拿固定地址），以后从常规网段就能管理，不必每次挂别名。

## 四、踩坑

- **探测循环里多个端口共用一个 `-o 文件`**：后面失败的端口会把先前抓到的页面覆盖成空文件，标题 grep 落空 → 得出「没有后台」的假结论。只取命中的那个端口，或每端口一个临时文件。
- **本地端口占用造成的假阳性**：端口转发报 `bind: Address already in use` 之后仍 `curl 127.0.0.1:PORT` 得到 200 → 打到的是本机无关服务。先换空闲端口，再用独立来源（如直接从路由器 curl 目标）比对内容确认是同一份。
- **BusyBox（iStoreOS）**：无 `cat -A`（用 `sed -n l`）、无 `diff`；`ping` 的 `-i` 只收整数且无 `-f` → 要样本量就加 `-c N` 配 `-q`，别试小数间隔和洪水模式。
- **`nslookup -type=AAAA` 对 CNAME 链可能返回空**：要判定 DNS 是否真返回 AAAA，用 `curl .../dns/query?type=AAAA` 或 `ping6 域名`。
