# OpenClash Rule Provider Setup

## 为什么用 Rule Provider

手动维护 `openclash_custom_rules.list` 的问题：
- 新服务被封时不会自动跟进
- 规则多了维护累
- 容易遗漏域名

Rule Provider 让 Clash 自动定期从远程拉取规则集，一次配置永久生效。

## 已有的 Rule Provider（ddrdog.yaml 中）

| 名称 | URL | 用途 |
|------|-----|------|
| ChinaMax | `api-gz.hosbbq.com/nus74f89st1/C.yml` | 国内直连 |
| Google | `api-gz.hosbbq.com/nus74f89st1/G.yml` | Google系代理 |
| YouTube | `api-gz.hosbbq.com/nus74f89st1/Y.yml` | YouTube代理 |
| OpenAI | `api-gz.hosbbq.com/nus74f89st1/CH.yml` | OpenAI代理 |
| SteamCN | `api-gz.hosbbq.com/nus74f89st1/SC.yml` | Steam国内直连 |

## 添加 GFW 封禁站点 Rule Provider

### 方案 A：使用公开规则集（推荐）

在 `ddrdog.yaml` 的 `rule-providers` 段添加：

```yaml
rule-providers:
  # ... 已有的 Google, YouTube 等 ...
  GFW:
    type: http
    behavior: domain
    url: https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/gfw.txt
    interval: 86400
    path: ./rule_provider/GFW.txt
 reject:
    type: http
    behavior: domain
    url: https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/reject.txt
    interval: 86400
    path: ./rule_provider/reject.txt
  direct:
    type: http
    behavior: domain
    url: https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/direct.txt
    interval: 86400
    path: ./rule_provider/direct.txt
  telegram:
    type: http
    behavior: ipcidr
    url: https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/telegramcidr.txt
    interval: 86400
    path: ./rule_provider/telegramcidr.txt
```

然后在 `rules` 段（MATCH 之前）添加：

```yaml
  - RULE-SET,reject,REJECT
  - RULE-SET,GFW,SSRDOG
  - RULE-SET,telegram,SSRDOG
  - RULE-SET,direct,DIRECT
```

### 方案 B：保持手动规则（当前方式）

当前 `openclash_custom_rules.list` 中的 60+ 条手动规则仍然有效。Rule Provider 和手动规则可以共存——手动规则优先级更高（在 custom_rules.list 中靠前）。

## 注意事项

1. **J4125 无 AVX2**：下载规则集时如果走 GitHub CDN 可能慢，用 jsDelivr 镜像
2. **规则集更新频率**：`interval: 86400` = 每24小时更新一次
3. **行为类型**：
   - `domain` = 每行一个域名后缀
   - `ipcidr` = 每行一个 IP/CIDR
   - `classical` = 完整规则格式（DOMAIN, IP-CIDR 等混合）
4. **验证规则加载**：`curl -s http://127.0.0.1:9090/rules -H 'Authorization: Bearer <PASSWORD>' | grep -o '"payload":"[^"]*"'`

## 参考

- [Loyalsoldier/clash-rules](https://github.com/Loyalsoldier/clash-rules) — 维护良好的中文规则集
- [SunnyNew/https-rule](https://github.com/SunnyNew/https-rule) — 另一个常用规则集
- 用户分享的 Clash Meta 规则维护指南中也推荐了 Rule Provider 方式
