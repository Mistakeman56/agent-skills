# OpenClash：抖音/B站 卡顿的真凶 = 规则集排序 + Fallback 组默认地区

## 症状
刷抖音/刷B站一卡一卡、加载不出来；但网络体检各项全正常（出口快、DNS 正常、无线干扰低）。

## 真因（实测确认 2026-10-04）
代理配置里存在这条规则：
```
RuleSet  TikTok  ->  TikTok 组
```
而 `rule_provider/TikTok.yml` **不只含 TikTok 国际版**，还包含字节系内外共用的核心域名：
```
snssdk.com / pstatp.com / ipstatp.com / isnssdk.com / ibyteimg.com / sgpstatp.com
```
→ **国内抖音的部分流量被抓去走代理**（`douyin.com` 本体命中 `ChinaMax -> DIRECT`，但上面这些域名命中 TikTok 规则集）。

再叠上组的默认地区：
```
[TikTok] type=Selector  now=SSRDOG   ← 手动选择器，之前停在 🇭🇰 Hong Kong
[Auto]   type=Fallback  all=[🇭🇰 Hong Kong, 🇨🇳 Taiwan, 🇯🇵 Japan, ...]  ← HK 排第一！
```
**香港节点连国内 CDN 绕路 → 卡；用户手动换成 🇯🇵 Japan → 立刻顺畅。**

## 诊断手法（关键）
1. **不要用关键字 grep `/rules` 就下结论** —— `rule-provider`（规则集文件）里的域名 grep 不到，必须去 `/etc/openclash/rule_provider/` 里查。
2. **看组的 type 和 `all` 顺序**：`Fallback` 取“第一个健康的”，所以**顺序 = 优先级**；`url-test` 取延迟最低。
3. `/connections` 快照只能反映当下，**抓不到短连接多的流量（抖音就是）**，别用它否定结论。
4. 判“抖音走不走代理”：查 `douyin`/`snssdk`/`pstatp`/`byteimg` 这几组域名分别命中哪条规则，而不是只看 `douyin.com`。

## ✅ 已实施的修复（2026-10-04）

### 铁证：同一测试 URL 下两个节点差 4.5 倍
```
GET /proxies/<name>/delay?url=http://www.gstatic.com/generate_204
  🇯🇵 Japan      → 60 ms   ✅
  🇭🇰 Hong Kong  → 271 ms  ⚠️
```

### 改法：把 `Auto`（fallback 组）的 Japan 提到首位
同时改**两个**文件（只改一个不够）：
- 源配置 `/etc/openclash/config/9.1.yaml` — OpenClash 重载时从这里重新生成
- 运行时 `/etc/openclash/9.1.yaml` — clash 进程实际 `-f` 加载的文件

源配置是单行内联格式，运行时是多行格式（emoji 用 `\U0001F1EF\U0001F1F5` 转义）→ **别用 patch/sed 硬改，直接拉回本地用 Python 重排列表，再 scp 推回**。

### ★ 热重载：不用重启进程（关键技巧）
```bash
curl -X PUT -H "Authorization: Bearer <secret>" -H "Content-Type: application/json" \
  -d '{"path":"/etc/openclash/9.1.yaml"}' "http://127.0.0.1:9090/configs?force=true"
# 返回 HTTP 204 = 成功；进程 pid 不变、规则数不变、防火墙/nftables 不动 → 风险极低
```
比 `/etc/init.d/openclash restart` 安全得多（后者会重建防火墙规则链，收敛 1–2 分钟）。

### 坑：`clash -t` 在本机校验会误导性报错
```
level=error msg="path is not subpath of home directory or SAFE_PATHS: /usr/share/openclash/ui"
configuration file ... test failed
```
**这是既有的 `external-ui` 路径限制，与改动无关** —— 别被它吓到、别为它去改配置。选 `SAFE_PATHS` 环境变量也压不住（会被默认值拼接）。**改用本地 PyYAML 自检 + 热重载后实际验证**。

### 备份位置
`/root/oc-fixjp-<时间戳>/`（含 `9.1.yaml.source`、`9.1.yaml.runtime`、`openclash.uci`）

## 修复（分两层，只做第一层必复发）

### 层次一 · 止痛：`Auto`(Fallback) 组改 **🇯🇵 Japan 排第一**，HK 挪后
任何流量掉到 Auto 都自动走日本。改 OpenClash 配置需重载，代理断 1~2 分钟。
**但这只是止痛** —— 抖音仍然绕道日本，节点一劣化、组一回落就再卡（已实测复发）。

### 层次二 · 治本：把字节系域名用 `DOMAIN-KEYWORD` 抢回 DIRECT
**必须排在任何 `RULE-SET` 之前。** 只写 `DOMAIN-SUFFIX,douyin.com,DIRECT` 挡不住 —— 规则集抓走的是另一批域名，结果是**视频 CDN 走直连、接口走代理**，两边不同步，照样卡。

```yaml
  - DOMAIN-SUFFIX,douyin.com,DIRECT
  - DOMAIN-KEYWORD,snssdk,DIRECT      # aweme.snssdk.com / is.snssdk.com ← 抖音核心 API
  - DOMAIN-KEYWORD,pstatp,DIRECT
  - DOMAIN-SUFFIX,amemv.com,DIRECT    # api.amemv.com
  - DOMAIN-SUFFIX,douyinvod.com,DIRECT
  - DOMAIN-SUFFIX,douyinpic.com,DIRECT
  - DOMAIN-SUFFIX,douyincdn.com,DIRECT
  - DOMAIN-SUFFIX,douyinstatic.com,DIRECT
  - DOMAIN-KEYWORD,byteimg,DIRECT     # 含 ibyteimg.com
  - DOMAIN-SUFFIX,bdxiguaimg.com,DIRECT
  - DOMAIN-SUFFIX,bdxiguastatic.com,DIRECT
  - DOMAIN-SUFFIX,zjcdn.com,DIRECT
  - DOMAIN-SUFFIX,toutiao.com,DIRECT
  - DOMAIN-SUFFIX,ixigua.com,DIRECT
  - DOMAIN-KEYWORD,bytedance,DIRECT
  - DOMAIN-SUFFIX,bytednsdoc.com,DIRECT
  - DOMAIN-SUFFIX,volccdn.com,DIRECT
```

**别怕“砍了伤国际版 TikTok”**：先看日志里有没有 `tiktokv.com`/`tiktokcdn.com` 这类国际版域名的连接 —— **没有就说明用户只用国内抖音，放心拉直连**（国内环境这是净收益）。

### 验证（改完必做）
```bash
# 关键词规则的 index 必须小于 RuleSet TikTok 的 index
curl -s -H "Authorization: Bearer <secret>" http://127.0.0.1:9090/rules | python3 -c "…"
# 真实连接日志应变为 match DomainKeyword(snssdk) using DIRECT
grep '<设备内网IP>' /tmp/openclash.log | grep -iE 'snssdk|douyin' | tail
```

### 层次三 · fake-ip 过滤：让国内 App 拿真实国内 IP
`fake-ip` 模式下**国内 App 也一样被解析成 `198.18.x.x`**，流量全部被送进内核中继。把它加进 `fake-ip-filter` 就变回**真实国内 CDN IP、直连出去** —— 少一跳、少一个故障点（QUIC 嗅探仍开着，域名照样还原，规则照样命中）。

两个文件都要改（和 Auto 组同一套：源 + 运行时）：
```
/etc/openclash/custom/openclash_custom_fake_filter.list   ← 持久源
/etc/openclash/9.1.yaml 的 dns.fake-ip-filter             ← 运行时
```
改完 `PUT /configs?force=true` 热重载 + `POST /cache/fakeip/flush` 清假 IP 缓存。

用 `+.domain.com` 前缀（**同时覆盖裸域和子域**，比 `*.` 可靠）。抖音系要覆盖的不止 `douyin.com`：
```
+.douyin.com +.snssdk.com +.pstatp.com +.ipstatp.com +.isnssdk.com
+.amemv.com +.douyinvod.com +.douyinpic.com +.douyincdn.com +.douyinstatic.com
+.byteimg.com +.ibyteimg.com +.bdxiguaimg.com +.bdxiguastatic.com
+.zjcdn.com +.toutiao.com +.ixigua.com +.bytedance.com +.bytednsdoc.com
+.bytedns1.com +.volccdn.com +.queniukw.com +.zwtianshangm.com +.cdnbuild.net
```
（后几个是 CDN CNAME 链上的真实域名，从 `/dns/query` 的 Answer 段挖出来）

**验证**：`nslookup aweme.snssdk.com 127.0.0.1` 从 `198.18.0.8` 变成 `203.0.113.1`（辽宁联通）即生效。

### ⚠️ 三层都做完仍卡时：不要再继续改代理
直连规则 + 本地 CDN 解析 + fake-ip 过滤都落地后若仍报卡，**代理侧已经没有可查的了**。按这个顺序转出去：

1. **先复核自己的测法**（`references/home-network-outage-forensics.md` 的「测量陷阱」一节）—— 内网测速仪、路由器本机 curl、`/connections` 快照都会给出**误导性的「一切正常」**。
2. 无线判据看 `references/ruijie-wio-optimization.md`（**看 min 延迟，不看 avg/max**；面板上的客户端 RSSI 可能是几小时前的旧值）。
3. **最后交给用户一个对照实验**：手机 Wi-Fi vs 手机流量刷同一个 App。流量下也复现 = 与家网无关（App / 服务端）；只在 Wi-Fi 下卡 = 回到无线侧。**这是唯一能一刀切开的证据**，比继续在路由器上翻配置有效得多。

### 已证伪的假设（别再重走一遍）
| 假设 | 证伪依据 |
|---|---|
| 手机 Wi-Fi 信号弱（AC 面板显示 -82dBm） | 用户手机跑出 665Mbps / 2ms / 抖动 1.29ms。**AC 客户端表带 `Last Updated` 时间戳，是缓存旧值** |
| `disable_udp_quic='1'` + `enable_udp_proxy='0'` 把全屋 QUIC 拦死 | nft 里有 `meta l4proto udp ip daddr 198.18.0.0/16 ... tproxy to 127.0.0.1:7895`，**counter 已转发数千包**；QUIC REJECT 是 `ip daddr != @china_ip_route`，**只打非中国真实 IP，国内目的地不受影响** |
| NAS BT 做种占满上传带宽 | WAN 实测下载 2–5Mbps / 上传 4Mbps（上限 90M），SQM `pk_delay 1.74ms` —— **链路 99% 空闲** |
| 日志里「零 UDP 连接」= UDP 路径是死的 | `/connections` 是瞬时快照，抓不到短流；**累计 counter 才是证据** |

**结论：该类投诉曾在「网络层全部指标健康」的状态下没有找到根因。** 不要为了给出交代把某个假设包装成「真凶」—— 按上面第 3 步把对照实验交给用户。

## 教训（写给自己）
**“网络体检全部正常”不等于“不是网络问题”。** 只查了 `douyin.com` 一条规则就断言“抖音全程直连”是错的 —— **大厂 App 用几十个域名，必须逐个查规则集。** 用户体感（换节点就好）比我的规则推断更可信。

**“换个更快的节点就好了”是止痛，不是治本：用户会再回来喊卡。** 看到国内 App 卡，先问“它的域名有没有被某个 `RuleSet` 抓走”，再用 `DOMAIN-KEYWORD` 抢回 DIRECT 并排到 RuleSet 之前。用户最初那句“抖音不应该直连吗”就是正解，别因为共用域名的顾虑把它推翻 —— 先查日志确认他是否用国际版，再决定。
