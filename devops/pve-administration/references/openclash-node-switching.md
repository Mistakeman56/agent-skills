# OpenClash 切节点 / 切国家 + 多地同条件测速

适用：「全都用 X 节点」「切过去试试网速」—— 把指定代理组固定到某节点/国家，用同一测法对比多地，交付对照表。

## 先判断走哪条路

1. **Clash API 正常就用 API**：`PUT /proxies/<组名>` body `{"name":"<节点>"}`，头 `Authorization: Bearer [REDACTED] secret）。
2. **恒 401（secret 明明对）= mihomo alpha 内核怪癖**：yaml `secret` 与 `uci openclash.dashboard_password` 同值、Bearer / 裸 token / query token 全试过仍 401 → **停止折腾认证，直接改配置**，别在 API 认证上耗时间。

## 改配置切换（API 走不通时的正路）

### 关键机制（不懂必踩坑）

- **restart 从订阅源重新生成运行时**（机制详见 `openclash-subscription-update.md`）→ 改动必须落到订阅源 `/etc/openclash/config/<name>.yaml`，只改运行时下次 restart 即丢。
- **`profile.store-selected: true`**：mihomo 把每组选择存进 `cache.db`（实为软链 → `/etc/openclash/history/<name>.db`），**启动时历史选择优先于配置 `now:`**。
- select 组没有可用历史时的默认 = **`proxies[0]`**。

### 步骤

1. 备份订阅源 + 运行时到 `/etc/openclash/backup/`（时间戳后缀，`/tmp` 重启即丢）。
2. **把目标节点提到目标组 `proxies[0]`，订阅源与运行时两份都改**：
   - 运行时是多行 `proxies:` 列表 → 调换 `- ` 行；
   - 订阅源常是内联 `{ name: X, type: select, proxies: [...] }` → 按**顶层逗号**切数组（引号内逗号不切），目标项移到最前，顺手给组补同名 `now:`。
3. `rm /etc/openclash/history/<name>.db`（`cache.db` 是指向它的软链，删目标文件即可）。
4. `/etc/init.d/openclash restart`（全屋断网 5~10 秒，属预期）。
5. **等 60 秒再验收**（watchdog 周期内旧选择可能还在）：

```sh
IP=$(curl -x http://127.0.0.1:7893 -s -m 10 https://api.ip.sb/ip)
curl -x http://127.0.0.1:7893 -s "https://api.ip.sb/geoip/$IP"   # 认 country/city 字段
ps w | grep -E '[c]lash' | grep -v watchdog                       # 进程恰好 1 个（防双进程竞态）
```

国家没变 → `grep -A6 'name: <组>' /etc/openclash/<name>.yaml` 看 `proxies[0]` 到底是谁，`grep 'using' <clash日志>` 看实际链路末端。

### PITFALL: `now:` 写对了也不生效（两层原因，都要处理）

1. history 文件在 → 启动直接用历史选择，`now:` 被无视 → 先删 `history/<name>.db`。
2. history 删了仍不认 → mihomo 回退 `proxies[0]`（实测 `now:` 与 proxies 里的名字**逐字节相同**照样不认）→ **生效手段认 `proxies[0]`，`now:` 只是补充**。

### PITFALL: 循环里给多个组插 `now:` 会互相抹掉

每个组插入前都跑一遍「删所有 `now:`」的全局正则，会把上一轮刚插的删掉，最后只剩最后一组。**删除动作放循环外只做一次**（或把正则限定在目标组块内）。

### PITFALL: 双进程竞态——「切完节点全家时好时坏/只看得见标题」的经典成因

手动 nohup 拉起 clash 时若 watchdog/procd 实例还活着，两个 mihomo 并存互抢 7893（代理）与 53（DNS 劫持），国内外流量随机走好走坏。**启动/切换后必验收进程数**：

```sh
ps w | grep -E '[c]lash' | grep -v watchdog   # clash 必须恰好 1 个
ps w | grep -E '[w]atchdog'                   # watchdog 恰好 1 个
```

发现 ≥2 → 连同 watchdog 一起全杀，**只走** `/etc/init.d/openclash restart` 补救，不许再补手动进程；也不要拿「出口 IP 对了」当健康——双进程时出口照样能测对。

### PITFALL: 手动拉起 clash 必须带 `SAFE_PATHS`

init.d 用 `procd_set_param env SAFE_PATHS=/usr/share/openclash:/etc/ssl`；手工 nohup 少了它，mihomo 会 fatal `path is not subpath of home directory or SAFE_PATHS: /usr/share/openclash/ui`（`external-ui` 在 home 外）：

```sh
SAFE_PATHS=/usr/share/openclash:/etc/ssl nohup /etc/openclash/clash \
  -d /etc/openclash -f /etc/openclash/<name>.yaml >>/tmp/clash_m.log 2>&1 &
```

仅作应急；正路仍是 `/etc/init.d/openclash restart`（只有它会重新生成配置并恢复 procd 环境）。

## 多地同条件测速（先确认出口已切成功）

- **网速**：`curl -x http://127.0.0.1:7893 -o /dev/null -w '%{speed_download}' -m 60 'https://speed.cloudflare.com/__down?bytes=10000000'`，每地 ≥2 轮。**`speed_download` 是 bytes/s** —— ÷1024² 才是 MB/s，×8/1e6 才是 Mbps，两个单位别写混。
- **延迟**：固定 2~3 个目标各 3 轮，读 `%{time_total}` + `%{http_code}`；状态判读（`401`=通未带 key、`403` cf challenge=通、`000`=超时）见 `openclash-subscription-update.md`。
- **每轮先复核出口 IP**：出口没变就是还在测旧节点，整表作废。
- 交付格式：「指标 × 地区」对照表 + 各地出口 IP/归属地 + 一句话结论（哪地适合哪类服务）。量级经验：同机场三地吞吐常差 2~3 倍；**某地对特定服务恒 403 = 该服务按 IP 拉黑了节点，不是配置错**。
- **切到哪国是用户决策**：测完报数据、保持当前状态待确认，不擅自定稿；用户明确授权（「先搞这个，我睡了」）才落地持久化。
