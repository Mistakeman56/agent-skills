# B站 视频「缓冲好了但卡住/卡顿」根因 = 网页端 PCDN（P2P 上传加速）

> 通用 PCDN 拦截手法（域名清单来源、fake-ip-filter bypass、Clash `hosts:` 黑洞、抖音/快手等）见同目录 `pcdn-blocking-and-fakeip-bypass.md`。本文件只记 B站 专项。

## 症状（一眼识别）
- 视频缓冲条已加载完，但画面卡死、不推进。
- WAN **下行 ≈ 0 Mbps**，而 Chrome 挂着 **多条 ESTABLISHED 到 B站 CDN/peer 的连接**，全是空转不吐数据。
- WAN **上行反而持续 5~60 Mbps**，PC conntrack **上传/下载比可达 24:1**。
- PC 上出现连到 **家庭宽带 IP** 的 TCP/UDP：判断铁证是 **PTR 反查含 `adsl` / `adsl-pool`**（例：`203.0.113.1` → `203.0.113.1.adsl-pool.sx.cn` = 山西联通家宽；`203.0.113.1` → `hn.kd.ny.adsl` = 河南联通家宽）。
- 非标端口连接（`7826`、`8082`、高位端口）：B站 PCDN 数据通道；`203.0.113.1`（京东云）= 京东云无线宝 PCDN 节点。

## 根因
B站 网页播放器启用 **WebRTC/PCDN**，把用户设备当分发节点：一边拉 peer 的流（peer 慢 → 卡死），一边**上传**给别人（吃上行，甚至触发运营商 PCDN 限速）。

## 关键坑（做错就白干）
**`*.mcdn.bilivideo.cn` 若写在 `openclash_custom_fake_filter.list` 里，它拿真 IP 直连、完全绕过 Clash —— 规则再怎么写也拦不到。**
必须**先把它从 fake-ip-filter 摘出来**，Clash 才能接管并 REJECT。

## 修法（已实测，2026-10-04）
1. 备份 `/etc/openclash/custom/openclash_custom_{rules,fake_filter}.list` + `/etc/openclash/9.1.yaml`。
2. `openclash_custom_fake_filter.list`：注释掉 `*.mcdn.bilivideo.cn`。
3. `openclash_custom_rules.list`：`bilibili.com` 那行之前插入
   ```
     - DOMAIN-SUFFIX,mcdn.bilivideo.com,REJECT
     - DOMAIN-SUFFIX,mcdn.bilivideo.cn,REJECT
     - DOMAIN-SUFFIX,szbdyd.com,REJECT
   ```
4. **同步运行时** `/etc/openclash/9.1.yaml`（删 fake-ip-filter 里那行 + 同样插 3 条，注意运行时 rules 前缀是 `- ` 不带缩进，custom 文件是 `  - `）。
5. 热重载（**不要 restart，会断网**）：
   ```
   curl -X PUT -H "Authorization: Bearer <secret>" -d '{"path":"/etc/openclash/9.1.yaml"}' 'http://127.0.0.1:9090/configs?force=true'
   ```
   204 = 成功。
6. 验证：`curl -H auth http://192.0.2.10:9090/rules | grep mcdn` 有规则；`nslookup mcdn.bilivideo.cn 127.0.0.1` **应查不到记录**；`szbdyd.com` 应回 `198.18.x.x`。
7. **必须让用户刷新 B站 页面**——已建立的 PCDN 连接不会自己断。

## 坑
- `clash_meta -t -f /etc/openclash/9.1.yaml -d /etc/openclash` 会报 `path is not subpath of home directory or SAFE_PATHS: /usr/share/openclash/ui` → **是 external-ui 的环境告警，不是配置错误**；以「热重载 204 + `/rules` 有规则 + 谷歌/百度能通」为准。
- 少数地区/劣质线路的冷门视频可能主流+备流都只有 MCDN，屏蔽后会无限加载 → 备份可一键回滚。
- DST-PORT,3478/5349 (STUN) 若在 custom_rules 里是 DIRECT，是给 Tailscale 留的，不是给 B站 PCDN 的。
