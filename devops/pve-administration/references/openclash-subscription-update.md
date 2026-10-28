# OpenClash 更新订阅链接（换机场订阅，自定义规则零丢失）

适用：用户给新订阅链接要求「弄到 openclash 里头」「我们写的规则啥的都要保留」，或协议升级换链。

## 核心机制（不懂这个必踩坑）

**`/etc/init.d/openclash restart` 会重新生成运行时配置。** 流程：

1. 读 `uci get openclash.config.config_path` 指向的**订阅源** `/etc/openclash/config/<name>.yaml`
2. `yml_change.sh` 注入 uci 端口/DNS 设置 + `custom/` 目录的自定义规则
3. 覆盖生成根目录的运行时 yaml（clash 启动命令 `-f` 指的就是这个生成物）

因此：**只改运行时 yaml 等于没改**，下次 restart 必被冲掉 —— 新订阅必须写进订阅源。
判断哪个是运行时：`tr '\0' ' ' < /proc/<clash-pid>/cmdline`。

## 操作步骤

```sh
# 1) 下载新订阅并测语法
#    URL 带 &：Python 生成脚本时用占位符 .replace('__URL__', url) 拼，
#    别用 f-string（shell ${...} 会让 f-string 炸），也别裸拼进 r'''...'''
curl -sL -m 30 -o /tmp/new_sub.yaml "$URL"    # 直连失败改走 -x http://127.0.0.1:7899 重试
/etc/openclash/clash -t -f /tmp/new_sub.yaml -d /etc/openclash   # 必须打印 "test is successful" 才继续

# 2) 备份订阅源 + 运行时，落 /etc/openclash/backup/（/tmp 重启即丢，别只放 /tmp）
mkdir -p /etc/openclash/backup
TS=$(date +%Y%m%d%H%M%S)
cp /etc/openclash/config/<name>.yaml "/etc/openclash/config/<name>.yaml.bak.$TS"
cp /etc/openclash/<name>.yaml "/etc/openclash/backup/<name>.runtime.bak.$TS"

# 3) 写入订阅源 + 重启（全屋断网 5~10 秒，属预期）
cp /tmp/new_sub.yaml /etc/openclash/config/<name>.yaml
/etc/init.d/openclash restart

# 4) 回读硬验证（全绿才收工；任一失败 = 备份拷回去 + 再 restart）
ps | grep '[c]lash -d'                          # 进程在
grep -c "新节点名" /etc/openclash/<name>.yaml     # 新节点真进来了
grep -c "tailscaled" /etc/openclash/<name>.yaml  # custom 规则还在
grep -m1 "^ipv6:" /etc/openclash/<name>.yaml     # ipv6: true 还在
grep -m1 "^secret:" /etc/openclash/<name>.yaml   # API secret 还在
```

**文件传输**：Hermes ↔ 路由器用 `scp -P 2222`（scp 端口是大写 `-P`，默认 22 会 `Connection refused`）；整段脚本走 `ssh -p2222 root@192.0.2.10 'sh -s' < file`（iStoreOS 只有 busybox sh，没有 bash/python，双层引号必炸）。

## 自定义规则为什么不会丢

- **`custom/openclash_custom_rules.list`**（uci `openclash.config.enable_custom_clash_rules=1`）：restart 时由 `yml_change.sh` 自动注入运行时配置 —— Tailscale 直连、OCSP 证书直连（不走代理否则 HTTPS 握手挂）、B站/抖音规则全在这里。
- **`SRC-IP-CIDR,192.0.2.X/32,DIRECT`** 局域网直连：同样自动重新生成。
- **端口/DNS/API**（mixed 7893、redir 7892、tproxy 7895、`secret`、`external-controller:9090`）：由 uci 注入，订阅里有没有都无所谓。
- → **正规更新订阅，以上一条都不用手工合并**；只有手工塞进运行时 yaml 的东西才会丢。手工维护两份 yaml 才是「删了旧配置全乱了」的根源（见 `openclash-config-mismatch-diagnosis.md`）。
- `ipv6: true` 也会被重新生成（按 uci `ipv6_enable`）—— 若 uci 是 0 而你之前手动改成 true，restart 后要再改一次并注意别再 restart（改 uci 属另一条红线，先问用户）。

## 验收：出口国家看出口 IP，不看组名

select 组可能压根没有 `now:`（默认取 proxies 列表第一个，fallback 组动态选），从配置读不出真实出口：

```sh
curl -x http://127.0.0.1:7893 -s -m 10 https://api.ip.sb/ip           # 走代理出口（7890=http 口、7893=mixed 口均可）
curl -x http://127.0.0.1:7893 -s -m 10 "https://api.ip.sb/geoip/$IP"  # 归属地/ISP
curl -s -m 10 --noproxy '*' https://api.ip.sb/ip                      # 裸连对照（应为家宽 IP）
```

- 出口落在 **`185.220.x`（公开 Tor 出口段）** 会让 Cloudflare/OpenAI 反复弹人机挑战并拖慢握手 —— 「网页老打不开要重试」可能根因是**节点 IP 声誉**而非线路。

## 慢/卡诊断：同 URL 的 A/B 计时，别猜

同一目标分别 `curl -x http://127.0.0.1:7893` 和 `curl --noproxy '*'`，读 `%{time_appconnect}`（TLS 握手）：

- 裸连明显更快 = 节点问题；
- 同一目标两次测出 0.6s 和 5.2s = 节点抖动（用户体感「时好时坏」）；
- 分域名差异大（同为代理下 api 0.6s / cdn 8.9s）= 走了不同规则路径或节点正在劣化；
- **HTTP 状态判读**：`403`（Cloudflare `cf-mitigated: challenge`）、`401`（API 未带 key）、`404`（CDN 根路径）都算「通了」，只有 `000` / `Connection refused` / `timed out` 才是不通。
