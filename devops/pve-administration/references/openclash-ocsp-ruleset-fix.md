# OpenClash 规则的隐形地雷：OCSP 证书服务被规则集吞去走代理

## 症状
- 微信小程序 / App 报「调用认证接口失败」「刷新 token 失败」
- 某些 HTTPS 站点握手慢到超时
- 路由、服务器本身都是好的（直连能通、ping 正常）

## 真因
**证书验证服务（OCSP/CRL）被“无关的规则集”误匹配，送去走了代理。**
实测这个家里抓到的：
```
ocsp.digicert.com:80   match RuleSet(Bahamut)  using 🇨🇳 Taiwan[台湾丨01]   ⚠️
ocsp.usertrust.com:80  match Match               using SSRDOG[🇯🇵 Japan丨04]  ⚠️
```
`Bahamut` 是**巴哈姆特（动漫站）** 规则集，里面竟然有 digicert —— 典型的规则集污染。
**证书校验必须直连**：走代理不仅慢，遇到节点不通时 TLS 握手会直接卡死/失败。

## 修法（两处都要改，才能既立即生效又持久）

### ① 持久的源：自定义规则文件
```
/etc/openclash/custom/openclash_custom_rules.list
```
（前提 `uci get openclash.config.enable_custom_clash_rules` = 1）

### ② 立即生效：运行时配置同位置同步
`/etc/openclash/9.1.yaml` 的 `rules:` 段
**⚠️ 关键：热重载 `PUT /configs` 只读 `/etc/openclash/9.1.yaml`，不会重新合并 custom 目录！**
只改 custom 文件 = 热重载后看不到效果，必须两边都写（或重启 OpenClash 触发重生）。

### 插入位置
放在 tailscale/IP-CIDR 块之后、任何 `RULE-SET` 之前。
**已验证的规则顺序**（自定义规则确实置顶，能压住规则集）：
```
[3]  DstPort 41641        ← 自定义规则从这开始
[12] DomainSuffix digicert.com → DIRECT   ← 新加的
[154] RuleSet Bahamut → 台湾
[170] Match → SSRDOG
```

## 推荐规则集（拷去即用）
```yaml
  # 证书验证服务(OCSP/CRL)：必须直连
  - DOMAIN-SUFFIX,digicert.com,DIRECT
  - DOMAIN-SUFFIX,usertrust.com,DIRECT
  - DOMAIN-SUFFIX,sectigo.com,DIRECT
  - DOMAIN-SUFFIX,comodoca.com,DIRECT
  - DOMAIN-SUFFIX,globalsign.com,DIRECT
  - DOMAIN-SUFFIX,globalsign.net,DIRECT
  - DOMAIN-SUFFIX,letsencrypt.org,DIRECT
  - DOMAIN-SUFFIX,entrust.net,DIRECT
  - DOMAIN-SUFFIX,identrust.com,DIRECT
  - DOMAIN-SUFFIX,verisign.com,DIRECT
  - DOMAIN-SUFFIX,thawte.com,DIRECT
  - DOMAIN-SUFFIX,geotrust.com,DIRECT
  - DOMAIN-SUFFIX,godaddy.com,DIRECT
  # Apple 全家直连
  - DOMAIN-SUFFIX,apple.com,DIRECT
  - DOMAIN-SUFFIX,cdn-apple.com,DIRECT
  - DOMAIN-SUFFIX,mzstatic.com,DIRECT
```

## 排查手法（找“到底哪个域名被走代理了”）
```bash
# 手机/某设备所有非 DIRECT 连接（全量去重）——规则缺口一眼现形
grep "192.0.2.10" /tmp/openclash.log | grep -oE "\-\-> [^ ]+ match [^ ]+ using [^ ]+" | sort | uniq -c | sort -rn
```
**判据：日志里只出现 `using DIRECT` ≠ 没问题，要看有没有“日得开的域名在走代理”。**

## ⚠️ 别急着下结论：先分清“客户端连不上” vs “厂商后台报错”
小程序报「调用XX认证接口失败」，可能是**厂商服务器自己调上游平台失败**，与家里网络无关。
**分界试验：让用户关 WiFi 用流量再试一次。** 流量下同样失败 = 厂商/平台问题，别在家里网络上白忙。
