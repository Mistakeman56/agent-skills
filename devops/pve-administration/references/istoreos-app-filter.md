# iStoreOS 应用过滤（OpenAppFilter）：按 App + 时间段封禁

目标形态：**某几个 App 在 00:00–07:00 全网不可用**。插件 = `appfilter`（引擎）+ `luci-app-oaf`（菜单「服务 → 应用过滤」），页面：`app_filter`/`time`/`user`/`feature`/`advance`。

## 红线（动手前先确认）

OpenClash / nftables 规则属用户禁改区。**拿到用户点头后**才碰 clash 的启停或规则；研究阶段一律只读 SSH（`ssh -o BatchMode=yes -p 2222 root@ROUTER`，端口 2222 才通）。

**名单+时段是 deliberately by the user配置、明确要求保留的防沉迷**：排查其它网络故障时「窗口内名单应用全黑」是设计行为不是故障——别 `rmmod oaf`/停服务当修复；要停或改名单先 `uci export appfilter > /root/appfilter.bak.$(date +%Y%m%d%H%M%S)` 备份并问一句。反过来，从「视频按点/挑应用全黑、路由器本机却全通」反查真凶的抓包判据（本地伪造 RST 的 ttl/时序/排除法）见 `network-slow-diagnosis.md` 的「动手前三问」与 oaf 段。

## 步骤

### 1. 探测现状

```bash
ssh -o BatchMode=yes -p 2222 root@192.0.2.10 '
  ubus call appfilter get_oaf_status;          # enable/engine_status/config_enable/match_time
  uci show appfilter | grep -E "enable|auto_load|rule|time"
  lsmod | grep "^oaf";                         # 内核驱动，auto_load_engine=1 才会载入
  uci get openclash.config.en_mode; nft list ruleset | grep redirect | head'
```

### 2. 打开关（LuCI「高级设置」勾的两项就是这两个）

```bash
ubus call appfilter set_app_filter_adv '{"tcp_rst":1,"lan_ifname":"br-lan","disable_hnat":1,"auto_load_engine":1}'
ubus call appfilter set_app_filter_base '{"enable":1,"work_mode":0,"record_enable":1}'
# work_mode: 0=Gateway(网关) 1=Bypass(旁路) —— 不是黑名单/白名单
```

### 3. 时间段（固定模式）

```bash
ubus call appfilter set_app_filter_time '{"mode":0,"weekday_list":[1,2,3,4,5,6,0],"time_list":[{"start":"00:00","end":"07:00"}]}'
# mode 0=Fixed(多段时间，time_list 为准) 1=Dynamic(allow_time/deny_time 学习-休息循环)
# 持久化在 uci: appfilter.time.time / .days / .time_mode
```

### 4. 选要封的 App（**数组**，见陷阱 1）

```bash
ubus call appfilter set_app_filter '{"app_list":[3001,3010,4001,4002,4012,3901]}'
ubus call appfilter get_app_filter      # 回读确认；空 user 列表 = 全网生效，无需逐设备加
```

### 5. 特征库（原厂库会缺 App，要自己补）

- 文件 `/etc/appfilter/feature.cfg`（`/tmp/feature.cfg` 是它的符号链接；引擎日志 `reload feature success` 即读到）
- 行格式 `ID 名称:[proto;sport;dport;host;url;dict]`，例如 `3001 抖音:[tcp;;;douyin;;,tcp;;;amemv.com;;]`
- **id 千位 = 分类**：1聊天 2游戏 3视频 4购物 5音乐 7下载 8常用网站；分类头形如 `#class video 3 视频`
- 加条目前先确认 id 空闲：`grep -E "^3[0-9]{3} " feature.cfg | awk '{print $1}' | sort -n`
- 改动必须先备份，再重启引擎生效：

```bash
cp -a /etc/appfilter/feature.cfg /etc/appfilter/feature.cfg.bak-$(date +%Y%m%d)
cat /tmp/new_feature.cfg | ssh -o BatchMode=yes -p 2222 root@ROUTER 'cat > /tmp/feature_new.cfg'  # 见陷阱 3
cp /tmp/feature_new.cfg /etc/appfilter/feature.cfg && /etc/init.d/appfilter restart
sleep 5; ubus call appfilter class_list | grep 目标App名   # 加载成功才继续
```

### 6. 验证三件套（缺一不可）

```bash
# (a) 时间窗内 match_time 必须是 1
ubus call appfilter get_oaf_status | grep match_time
# (b) 分类真认出来: 先 curl 目标站，再按 MAC 查记录
for u in https://www.douyin.com https://www.bilibili.com; do curl -sS -o /dev/null -m 6 --noproxy '*' "$u"; done
ubus call appfilter dev_visit_time '{"mac":"<设备MAC>"}'   # list 出现目标 App 才算识别
awk 'NR>1 && $2!=0' /proc/net/af_visit                      # 内核侧分类计数，全 0 = 没在识别
# (c) 阻断真生效: 对照站必须通、目标站必须失败
for u in https://www.baidu.com https://www.douyin.com; do curl -sS -o /dev/null -w '%{http_code}' -m 6 --noproxy '*' "$u"; done
```

## 分类正常却拦不住 → 查流量路径，别继续调配置

识别走**本地投递路径**、阻断走**转发路径**，是两回事。分类对、`match_time=1`、规则齐却全通，根因几乎一定在 nat PREROUTING 劫走了流量：

```bash
nft list ruleset | awk '/chain openclash \{/,/^\t\}/'
# 有 'ip protocol tcp ... redirect to :7892' 且没有 'ip daddr @china_ip_route return' = 全量被劫
```

OpenClash 接管后 OAF 读不到报文（上游作者原话：「流量被 clash 接管后 OAF 无法解析数据报文」），此时调 oaf 无用。给用户四个选项让他选，**不要自作主张碰 clash**：

| 选项 | 代价 |
|---|---|
| 夜间定时停/启 OpenClash（与封禁时段重合） | 只动启停不动规则，期间无代理 |
| 国内流量直连（redir-host + 绕过中国大陆 / fake-ip-filter） | 动 clash/nft，红线，需授权 |
| 设备级「屏幕使用时间」 | 零风险但非全网 |
| 另装「上网时间控制」`luci-app-timecontrol` | 同样写防火墙，大概率撞同一个劫持 |

## 陷阱

1. **`set_app_filter` 的 `app_list` 必须是 JSON 整数数组**。传逗号字符串会让 oafd 在 `libjson-c` 空指针 **segfault**（`logread | grep segfault`），进程被 procd 拉起但规则没落盘。ubus 返回 `{}` = 成功，回读用 `get_app_filter`。
2. **重启 oafd 后立刻回读 `match_time`**，为 0 就把时间配置重推一次再确认——状态可能还停在旧判定。
3. **给路由器传多行脚本用 `ssh ROUTER 'sh -s' < 本地文件`**。把换行塞进命令行参数（Python `repr()`/`\n` 字面量）会被 ash 当普通字符，报 `necho: not found` 这类怪错。传文件用 `cat 本地 | ssh 'cat > 远端'`：busybox **没有 base64**，两边核对**字节数**（`wc -c`），别拿 Python `len()` 字符数比——UTF-8 中文会差上千字节。
4. **空 `user` 列表 = 全网生效**。`add_app_filter_user` 返回 `Unknown error -1`（参数结构与文档不符），全网场景根本不需要加设备。
5. **引擎会偶发掉分类**：`/proc/net/af_visit` 的 appid 全 0 且日志没有新分类时，先 `/etc/init.d/appfilter restart`（`modprobe` 对已加载模块是 no-op，必要时先 `rmmod oaf`）；再回滚特征库复测，以排除是不是自己改的文件导致的。
6. **原厂特征库会缺 App**（如 B站；闲鱼真域名 `goofish.com` 不匹配 `xianyu`），识别不到就等于没封——别误判成规则没下发。
7. **「我用的是真实国内 IP，应该没被劫持」是错觉**：`chain openclash` 的 `ip protocol tcp ... redirect` 不区分国内/国外（没有 `@china_ip_route return` 就是全量劫），而且 `uci get openclash.config.china_ip_route` 返回 1 也只代表那个 IP 集被用于 QUIC 排除。出口真不真 IP 与流量走不走转发路径无关。
