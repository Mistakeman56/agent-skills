# 内网设备清点 → DHCP 静态绑定与命名标记

用途：用户说「我网络里应该有一台某牌的 AC 和 N 台 AP，给我找出内网 IP」「把这些 IP 固定住并在软路由里标记一下」时，从零把设备认出来并钉死地址。

## 认设备

顺序：**先全量取表 → 再按厂商过滤 → 最后用主机名定角色**。

1. 取全量在线表（两张表都要，互补）：
   - DHCP 租约（**带主机名**，最强证据）：`cat /tmp/dhcp.leases`（OpenWrt/iStoreOS）→ 字段 `租期 MAC IP hostname clientid`
   - ARP 表：`ip neigh show | grep -v FAILED`（含更多在线但无租约的设备）
2. **按 OUI 批量查厂商**，不要只查一个前缀：
   ```sh
   curl -s -m 8 --noproxy '*' https://api.maclookup.app/v2/macs/<OUI6位>
   # → {"found":true,"company":"Ruijie Networks Co.,LTD",...}
   ```
   ★ 同一厂商常有多个 OUI 段：5 台锐捷里 4 台是 `70:42:D3`、第 5 台是 `9C:2B:A6`。**先把 ARP 里所有 MAC 去重成唯一 OUI 列表，再逐个查**；只查出现次数最多的那一段会漏设备（也就能解释「你说 4 台我怎么数出 5 台」）。
3. **用主机名定角色**：AP 的租约名形如 `EAP262E-1D8940`，AC/网关形如 `EG210G-P-E-6BD0CC`。型号前缀 + MAC 后六位就是设备身份；AC 常是「网关 + 内置网络控制器(AC) + PoE 供电」一体机（如 RG-EG210G-P，8 个 PoE 口带 AP）。
4. 交叉验证：这类设备的 80/443 普遍返回 200（管理页），端口探测不要用 1 秒超时（会全判失败）；`curl -sk https://<ip>/` 看页面/机型。

输出给用户时列成表格：**IP ／ 主机名 ／ 型号 ／ 角色（AC or AP）／ MAC**，并说明哪台是 AC。

## 钉住 IP + 命名标记（iStoreOS / OpenWrt）

「IP 不变」= **路由器侧 DHCP 静态租约**（不动设备配置）；「标记」= 租约的 `option name`。

```sh
cp /etc/config/dhcp /etc/config/dhcp.bak.$(date +%Y%m%d-%H%M%S)
uci add dhcp host
uci set dhcp.@host[-1].enabled='1'
uci set dhcp.@host[-1].mac='00:00:00:00:00:00'
uci set dhcp.@host[-1].ip='192.0.2.10'
uci set dhcp.@host[-1].name='ruijie-ac-eg210g'   # 标记名，ASCII 字母/数字/连字符
uci commit dhcp
/etc/init.d/dnsmasq restart
```

- 加之前查重，避免同一 MAC/IP 两条冲突：`uci -q show dhcp | grep "mac='<MAC>'"` / `grep "ip='<IP>'"`。
- **纯追加，不改写既有 `config host`**（那些可能属于别的设备）。
- 只在 `dnsmasq` 服务重启，不动防火墙；重启后**确认 dnsmasq 进程还在**，没起来就 `cp` 回备份重来。
- 备份是`/etc/config/dhcp`级别，回滚 = 拷回 + `uci commit dhcp` + 重启 dnsmasq。

## 验收

- 名字解析（在路由器上、并**指明路由器为 DNS**）：
  ```sh
  nslookup ruijie-ac-eg210g 127.0.0.1   # → Address: 192.0.2.10（返回名会带 .lan 后缀）
  ```
- 租约表里出现标记名：`grep -i <oui> /tmp/dhcp.leases`
- ARP 里 IP 未变。

## 坑

- **在 Hermes 主机上 `getent hosts <name>` / `ping <name>` 失败是正常的**：本机 resolver 走公共 DNS，公共 DNS 不知道内网的 `.lan` 域名。要验就用 `nslookup <name> 192.0.2.10`。别把它写成故障。
- **`config host` 的 IP 可以落在 DHCP 池范围内**（OpenWrt 绑定优先级高于动态分配），不必改 `start/limit`。
- 改 UCI 用 `commit` + 重启对应服务，**绝不** `fw3 flush` / 整机 reboot。
- DHCP `name` 要 ASCII（hostname 规范），中文标记会出问题 → 用拼音/英文（如 `ruijie-ap-117`）。
- OUI 查询走公网 API：拉取时要 `--noproxy '*'`，否则本机代理会拦掉；批量查询时**按唯一 OUI 去重**，别对每台设备重复查。
- 路由器/iStoreOS 是 BusyBox：`base64` 不存在，脚本一律「本地 `write_file` + `scp`」传，不要试图用 base64 管道。
