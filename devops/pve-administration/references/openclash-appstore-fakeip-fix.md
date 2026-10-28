# App Store 下不动 —— fake-ip 没排除苹果域名

## 症状
iPhone 在 App Store 点下载永远卡在「等待中」/转圈；但浏览器、微信、抖音都正常。
苹果的 App Store **API** 请求看着都成功（bag.itunes / amp-api 有数据流），**就是下载不动**。

## 真因
App Store 的下载域名被 **fake-ip 化**了：
```
iosapps.itunes.apple.com          -> 203.0.113.1   ⚠️假IP
downloaddispatch.itunes.apple.com  -> 198.18.x.x   ⚠️假IP
appldnld.apple.com / apps.apple.com -> 198.18.x.x  ⚠️假IP
```
短连接的 API 每次都重新解析 → 正常；**下载是长连接**，客户端握着**旧的**假 IP 映射（`store_fakeip=1` 会让映射粘住）→ 连到失效的假 IP → 卡死。

## 修复位置（持久）
OpenClash 的自定义 fake-ip 过滤列表：
```
/etc/openclash/custom/openclash_custom_fake_filter.list
```
该文件里 `#geosite:apple-cn` **默认是被注释掉的** —— 这就是病根。改成：
```
#App Store 下载
geosite:apple-cn
*.itunes.apple.com
apps.apple.com
*.mzstatic.com
*.cdn-apple.com
amp-api-edge.apps.apple.com
amp-api.apps.apple.com
app-site-association.cdn-apple.com
```
（该目录下还有 `openclash_custom_fake_filter.list.bak.*` 可对照）

## 立即生效（不用重启）
同晚改运行时配置 `/etc/openclash/9.1.yaml` 的 `dns.fake-ip-filter` 块，然后：
```bash
# ① 热重载配置
curl -X PUT -H "Authorization: Bearer <secret>" -H "Content-Type: application/json" \
  -d '{"path":"/etc/openclash/9.1.yaml"}' "http://127.0.0.1:9090/configs?force=true"

# ② 清掉旧的假 IP 映射（关键！否则老映射还粘着）
curl -X POST -H "Authorization: Bearer <secret>" http://127.0.0.1:9090/cache/fakeip/flush
```

## 验收方法（一眼判定）
```bash
nslookup iosapps.itunes.apple.com 127.0.0.1
#   修复前: 203.0.113.1            ❌
#   修复后: 203.0.113.1          ✅ 真 IP（阿里云 CDN: *.m.alikunlun.net）
curl -s -o /dev/null -w "%{http_code} %{size_download}B %{speed_download}B/s\n" -L https://apps.apple.com/
#   应能真下到数据（code=200，数百 KB/s）
```
校验路由：`/connections` 里苹果流量必须 `RuleSet/ChinaMax → DIRECT` 或 `IPCIDR/17.0.0.0/8 → DIRECT`。

## ⚠️ 最后一步只能用户自己做
**路由器清了 fake-ip 缓存，清不掉手机自己的 DNS 缓存。**
必须让用户 **关 WiFi 再开**（或开关飞行模式），否则手机还拿着旧假 IP。
**只改服务端不通知用户 = 看起来没修好。**

## 安全性（为什么这改动风险低）
苹果域名拿真 IP 后仍会走直连，有三重保险：
1. `sniffer` 已开（TLS:443 + `override-destination: true`）→ 能从 SNI 还原域名 → 再匹配 `RuleSet ChinaMax`
2. 苹果中国 CDN 的 IP 本身就是国内段 → `GeoIP cn → DIRECT`
3. `IPCIDR 17.0.0.0/8 → DIRECT`（苹果自带网段）
