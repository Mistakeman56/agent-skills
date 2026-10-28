# DDNS 覆盖：主域 / 泛解析 / AAAA 自建同步

## 为什么要自己做

路由器上 `ddns-scripts_aliyun` 的每条 `config service` 都是**逐个主机名**配的（`domain '主机@域名'`）。它只维护当初列进去的那批子域，**`@`（主域）和 `*`（泛解析）通常不在里面**。

后果：联通 PPPoE 重拨换 IP 后，子域全部自动跟上，**主域名和泛解析还指着旧 IP** → 「子域名能开、裸域名打不开」，而公共 DNS 还有 TTL 缓存，看起来像随机故障。

另外 IPv6 前缀也会在重拨时变（`20a1:5cf0` → `20a3:5570`，地址是 EUI-64 跟着变），所以 `@` 的 AAAA 也必须跟着同步。

## 两个可用的轮子

| 脚本 | 职责 |
|---|---|
| `~/.hermes/scripts/aliyun-dns.py` | 阿里云 DNS API 封装。读 `~/.hermes/.aliyun.env` 的 **`Ali_Key` / `Ali_Secret`**（不是 `ACCESS_KEY_ID`）；内部用 `build_opener(ProxyHandler({}))` 绕代理；提供 `list` / `api(Action, params)` |
| `~/.hermes/scripts/ddns-sync.py` | 全量同步：所有 A → 当前 IPv4；`@` 的 AAAA → 本机全局 IPv6。挂 cron `*/5` |

（早期还用过只同步 AAAA 的 `ddns-aaaa.py`，已被 `ddns-sync.py` 取代。）

## ddns-sync.py 的三个要点

```python
# 1) 公网 IPv4 从路由器取 —— 不要调外部 API（会被本机代理环境变量坑）
subprocess.check_output([
    "ssh", "-p", "2222", "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=8",
    "-o", "BatchMode=yes", "root@192.0.2.10",
    "ifconfig pppoe-wan | grep -o 'inet addr:[0-9.]*' | cut -d: -f2"])

# 2) 本机全局 IPv6（EUI-64）
subprocess.check_output(["ip", "-6", "addr", "show", "scope", "global"])
#   从输出里挑 2408: 开头且不以 fd 开头的地址

# 3) 遍历 DescribeDomainRecords，逐条 UpdateDomainRecord 改写不一致的
#    只动 Type in (A, AAAA)，TTL 固定 600
```

**幂等**：值一致就跳过，全一致时打印一行「全部已是最新」——这样日志可以直接当健康信号看。

## 部署

```sh
crontab -l | grep -v ddns   # 先看旧的有没有残留
crontab -e                  # 只留一行：
*/5 * * * * /usr/bin/python3 ~/.hermes/scripts/ddns-sync.py >> /var/log/ddns-sync.log 2>&1
```

## 验证

```sh
# 脚本自己能跑通、输出「已更新」或「全部已是最新」
python3 ~/.hermes/scripts/ddns-sync.py

# 权威 vs 公共（两者不一致 = 还在 TTL 缓存期，不是没改成功）
dig +short @dns29.hichina.com 域名 A
dig +short @203.0.113.1      域名 A
dig +short @192.0.2.10  域名 A      # 路由器 dnsmasq，家里设备用的就是这个
dig +short @dns29.hichina.com 泛解析测试名.域名 A   # 验泛解析

# 日志尾部没 traceback
 tail -3 /var/log/ddns-sync.log
```

## 坑

- **阿里云免费版 TTL 最低 600 秒**：`UpdateDomainRecord` 传 `TTL=60` 直接返回 `HTTP 400 Bad Request`，降不下来。改完 10 分钟内公共 DNS 仍是旧值，**别下「没改成功」的结论**。
- **`Connection refused` = 走了本机代理**，不是阿里云挂了（见 `public-reachability.md`「自写脚本的坑」）。
- **改完记得清本地缓存**再测：`kill -HUP $(pidof dnsmasq)`（本机 + 路由器各一次）。
- **cron 里跑的一定要落日志**，否则静默失败一整个晚上没人知道。
