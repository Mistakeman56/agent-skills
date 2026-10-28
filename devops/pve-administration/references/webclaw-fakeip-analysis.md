# webclaw fake-IP 不兼容根因分析

## 问题现象
```
webclaw scrape https://github.com/0xMassi/webclaw
→ Error: Fetch failed: invalid url: URL resolves to a blocked private or internal address
```

## 根因

### 调用链
1. webclaw 收到 URL `https://github.com/0xMassi/webclaw`
2. 调用 `validate_public_http_url()` (url_security.rs)
3. 对域名 `github.com` 做 DNS 解析
4. LXC 200 的 DNS 请求被路由器劫持到 Clash (fake-ip 模式)
5. Clash 返回 `198.18.x.x` (从其 fake-ip 池分配)
6. `validate_url_host_is_public()` 遍历解析到的所有 IP
7. 对每个 IP 调 `reject_blocked_ip()`
8. `is_blocked_ipv4()` 命中: `(o[0] == 198 && (18..=19).contains(&o[1]))`
9. 返回 `FetchError::InvalidUrl("URL resolves to a blocked private or internal address")`

### 关键代码 (crates/webclaw-fetch/src/url_security.rs:98)

```rust
fn is_blocked_ipv4(ip: Ipv4Addr) -> bool {
    let o = ip.octets();
    ip.is_unspecified()
        || ip.is_loopback()
        || ip.is_private()           // 10.x, 172.16-31.x, 192.168.x
        || ip.is_link_local()        // 169.254.x
        || o[0] == 0
        || o[0] >= 224               // multicast + reserved
        || (o[0] == 100 && (64..=127).contains(&o[1]))  // CGNAT 100.64-127.x
        || (o[0] == 192 && o[1] == 0 && o[2] == 0)      // IETF 192.0.0.x
        || (o[0] == 192 && o[1] == 0 && o[2] == 2)      // 192.0.2.x TEST-NET
        || (o[0] == 198 && (18..=19).contains(&o[1]))    // ← 198.18.x Benchmarking  ← HIT!
        || (o[0] == 198 && o[1] == 51 && o[2] == 100)    // 198.51.100.x TEST-NET-2
        || (o[0] == 203 && o[1] == 0 && o[2] == 113)     // 203.0.113.x TEST-NET-3
}
```

**Clash 的 fake-ip 范围默认 `198.18.0.1/16`**，恰好落在 IETF RFC 2544 基准测试保留段 `198.18.0.0/15`，被 webclaw 的 SSRF 防护精确拦截。

## 绕过可能性

| 方法 | 可行？ | 原因 |
|------|:--:|------|
| 环境变量 | ❌ | 无相关读取 |
| CLI 参数 | ❌ | `--help` 中无 skip/allow/unsafe 选项 |
| 配置文件 | ❌ | 无 IP 白名单配置 |
| 修改源码重新编译 | ✅ | 注释掉 `198.18` 行即可，但不安全 |
| 把 DNS 指向真实 DNS | ❌ | 路由器劫持所有 53 端口流量 |
| 本地 DoH 代理 | ⚠️ | 之前尝试 cloudflared 失败（TLS 握手被代理拦截） |
| 换 redir-host | ✅ | 但影响全家设备 |

## 结论
webclaw 的设计假设是"不使用透明代理"或"透明代理不返回保留 IP"。Clash fake-ip 正好打破了这个假设。**已从 LXC 200 卸载。**

### 替代方案（已实测）
1. **`mcp_fetch_fetch`**（首选）—— 走 HTTP 代理不做 DNS 校验，GitHub/Rust Blog 等均通
2. **Firecrawl MCP**—— 云服务，自带出口。需 API key，免费层 500 credits/月
3. **自部署 Jina Reader**—— 需 Docker + headless Chrome，⚠️ 官方托管版 `r.jina.ai` 从中国不通（Cloudflare 拦截 SSRDOG 代理 IP）
4. **换 redir-host**—— 不推荐，为单一工具动全屋 DNS 得不偿失

### 更多工具替代矩阵
详见 `references/tool-alternatives.md`（含实测矩阵）。
