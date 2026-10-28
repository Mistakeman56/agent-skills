# OpenClash DNS模式选择：fake-ip vs redir-host

## 决策树

```
OpenClash DNS出问题了？
├── DNS全挂（所有设备打不开网页）
│   ├── enable_redirect_dns=1? → 关掉（=0），DNS走ISP
│   └── fake-ip模式? → 改redir-host
├── 部分域名解析慢
│   └── 检查OpenClash DNS上游是否可达
├── 游戏/应用间歇性卡顿
│   └── 检查MATCH规则是否把流量走代理
└── Tailscale打洞失败
    └── fake-ip会干扰DERP发现 → 改redir-host或加fake-ip-filter
```

## 两种模式对比

| | fake-ip | redir-host |
|---|---|---|
| DNS解析 | OpenClash返回假IP(198.18.x.x) | 返回真实IP |
| 代理匹配 | 通过假IP→OpenClash内部映射→规则 | 通过SNI/Host头→规则 |
| DNS稳定性 | ❌ 依赖OpenClash DNS链 | ✅ DNS和代理解耦 |
| 翻墙效果 | ✅ 最佳（无DNS污染） | ✅ 正常（SNI嗅探） |
| 适用场景 | 稳定环境，不常断网 | 不稳定环境，频繁重拨 |

## 什么时候fake-ip会出问题

1. **PPPoE断线重连**：OpenClash重启时DNS劫持规则先于PPPoE就绪，导致死循环
2. **换光猫/换网线**：同上，物理层中断触发连锁反应
3. **Tailscale/VPN共存**：假IP干扰VPN的DERP/STUN发现
4. **订阅更新**：新订阅可能改MATCH行为，间接影响DNS体验

## 历史记录

- 2026-05-11：fake-ip + DNS劫持导致Tailscale打洞失败，用nftables精确绕过修复
- 2026-07-02：换光猫后DNS死循环，改为redir-host + 不劫持DNS，彻底解决

## 修复命令模板

```bash
# 切换到redir-host + 不劫持DNS
ssh -p 2222 root@192.0.2.10 "
uci set openclash.config.enable_redirect_dns='0'
uci set openclash.config.redirect_dns='0'
uci set openclash.config.en_mode='redir-host'
uci set openclash.config.operation_mode='redir-host'
uci commit openclash

CONFIG=\$(uci get openclash.config.config_path)
sed -i 's/en_mode: fake-ip/en_mode: redir-host/' \$CONFIG
sed -i 's/operation_mode: fake-ip/operation_mode: redir-host/' \$CONFIG

/etc/init.d/openclash restart
"
```
