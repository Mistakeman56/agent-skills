# 局域网设备清点 · 厂商识别 · IP 固定

适用：找出某品牌的一批设备（AC/AP/NAS/摄像头）、给它们起能记住的名字、并让 IP 永不变。

## 步骤

1. **两个数据源先拿全**（在路由器上）：
   ```sh
   ip neigh show                      # 在线设备 IP ↔ MAC（含 STALE/REACHABLE）
   cat /tmp/dhcp.leases               # 时间戳 MAC IP 主机名 —— 主机名是最便宜的身份线索
   ```
   DHCP 租约里的主机名常常直接暴露型号与角色（`EAP…` = 无线 AP、`EG…` = 网关/AC 一体机、`DXP…` = NAS），**先读主机名再考虑扫端口**。
2. **批量识别厂商**：把 ARP 里所有 MAC 取**前三字节去重**后逐个查 OUI，避免每台设备重复请求：
   ```sh
   curl -s -m 8 'https://api.maclookup.app/v2/macs/7042D3'
   ```
   命中目标厂商（如 `Ruijie Networks`）的条目即候选；本机无 OUI 库时不要靠记忆断言厂商。
3. **区分角色**：`curl -sk -m 4 -o /dev/null -w '%{http_code}' http://<ip>/` 探 80/443/8443，能开的就是有管理界面的；产品资料确认某型号是否「内置网络控制器（AC）」，PoE 口数与 AP 数量对得上即可判定。
4. **固定 IP + 打标记**（iStoreOS / OpenWrt）：
   ```sh
   cp /etc/config/dhcp /etc/config/dhcp.bak.$(date +%Y%m%d-%H%M%S)
   uci add dhcp host
   uci set dhcp.@host[-1].enabled='1'
   uci set dhcp.@host[-1].mac='00:00:00:00:00:00'
   uci set dhcp.@host[-1].ip='192.0.2.X'
   uci set dhcp.@host[-1].name='brand-role-<末段>'
   uci commit dhcp
   /etc/init.d/dnsmasq restart        # 只重启 dnsmasq，绝不动防火墙
   ```
5. **验收**：`nslookup <name> 127.0.0.1` 解析到预期 IP；`/tmp/dhcp.leases` 里出现带名字的条目；`ip neigh` 的 IP 与改前一致。

## 坑

- **IP 必须落在 DHCP 池内**（`config dhcp 'lan'` 的 `start` + `limit`），池外的绑定不生效；先确认现有 `config host` 有没有同 MAC/同 IP 的条目，避免重复。
- **name 会变成 DNS 主机名，只能 ASCII**（字母数字+连字符），中文会解析失败；想表达用途用拼音/型号缩写。
- 静态租约是**保留**不是迁移：设备当前 IP 不变，只有它重新申请时才会被强制回该 IP。
- **本机 `ping <name>` 失败不等于绑定失败**：宿主机 resolver 指向公共 DNS 时它不知道内网域（`name.lan`），而 `nslookup <name> 192.0.2.10` 能通 —— 判定以**路由器 DNS 能否解析**为准，因为客户端的 DNS 由 DHCP 下发到路由器。
- 改 DHCP 前后都要留时间戳备份；语法检查（`uci show dhcp`）通过再重启，失败立即 `cp` 回滚。
