# PCDN 拦截 + 穿透 OpenClash fake-ip-filter bypass

## 何时用
用户说「B站/抖音/视频卡住了」「上行被偷跑」「缓冲好了但画面不推进」「宽带被当 PCDN 节点」。

## 一、先确认是不是 PCDN（30 秒判据）
1. **卡住时 WAN 下行 ≈ 0，但客户端挂着一堆 ESTABLISHED 到 CDN/peer 的连接**（空转不吐数据）。
2. **WAN 上行持续 5~60 Mbps，下载/上传比可达 24:1**。
3. **铁证 = PTR 反查含 `adsl`**：例 `203.0.113.1` → `203.0.113.1.adsl-pool.sx.cn`（山西家宽）、`203.0.113.1` → `hn.kd.ny.adsl`（河南家宽）。**PCDN 节点就是别的用户的家用宽带。**
4. 非标端口（7826/8082/高位端口）+ `116.196.x`（京东云无线宝）也是 PCDN 特征。
5. **B站 PCDN 专有域名**：`*.mcdn.bilivideo.com` / `*.mcdn.bilivideo.cn` / `szbdyd.com` / `bvc.bilivideo.com`。

## 二、域名清单权威来源
`https://github.com/1-Reality/China-PCDN-Rules`（光复网路计划，哥哥科技）
- 取 `generated/PCDN域名.tsv` → 有 **置信度分级**（`font_rgb`/`fill_rgb`/`note` 列）。
- **只用黑色加粗（高置信度）**。TSV 分级：
  - 黑加粗 B = 高置信度「流氓必屏蔽」→ 默认全量部署
  - 蓝 B = 极客注意（stun/turn/rtc/peer/chunk/upload/tracker）
  - **红 = 高危测试，极易引发大面积业务异常 → 必须跳过**
  - 黄 = 低置信度；白 = **已知误伤**（`scdn`影响WPS小红书、`twns`影响Q音、`live`影响穿越火线、`ac.dun`=网易易盾）
- **绝不能拦**：`amemv`、`snssdk`、`pstatp`、`volcvideo`、`douyinvod`、`bytegoofy` —— 是抖音/字节的**播放入口**，拦了就是无限加载。
- **落盘前逐条过「域名语义门」**（唯一判据，完整表见三·九）：含 `p2p`/`peer`/`chunk`/`stun.` = 该黑；含 `flive`/`rtmp`/`live`/`pull-`/`push-`/`flv` = **播放/推拉流链路，一律不黑**。**别拿「能解析出真 IP」当 PCDN 证据 —— 真 IP 恰恰说明它是正经 CDN。**
- **名单之外新增，一次别超过个位数，且必须双向验收**：目标域变 `127.0.0.1` **且** 播放链路（`www.douyin.com`、`v3-web.douyinvod.com`、`pull-*.flive.douyincdn.com`、`www.bilibili.com`）仍回真 IP。一键审计：`scripts/audit-pcdn-blocklist.sh`。
- ADGHome.txt 里的 `@@||...^` 行是**白名单**（放行），别当拦截规则。

## 三、★★★ 核心坑：OpenClash 的 fake-ip-filter 会让规则完全失效
若域名命中 `fake-ip-filter`，Clash **返回真 IP**，客户端直连、**根本不进 Clash**，所以：
- `DOMAIN-SUFFIX,xxx,REJECT` 规则 **对它们无效**（引不起任何报错，静默失效）
- 实际环境里这层 bypass 有两处：
  1. 显式条目（如 `+.douyincdn.com`、`+.douyinvod.com`）
  2. **`rule-set:oc-cn-domain`** —— 整个 geosite cn 列表！等于「**所有国内域名都绕过 Clash**」（性能优化，别擅删：J4125 类软路由会让全国内流量上 CPU）
- **先验证再动手**：`nslookup <域名> 127.0.0.1` → 回 `198.18.x.x`=走 Clash（能拦）；回真实国内 IP=已 bypass（拦不到）。

### 试过但失败的两条路（别再走）
- ✗ 在 fake-ip-filter 里写更具体的 `+.flive.douyincdn.com 0.0.0.0` → **压不过父级 `+.douyincdn.com`**，仍回真 IP。
- ✗ 只加 REJECT 规则 → bypass 流量不进 Clash，规则永不匹配。

### ✅ 唯一有效：Clash 的 `hosts:`（DNS 解析路径最前，优先于 fake-ip 和上游）
OpenClash 的 `openclash_custom_hosts.list` 会被 `yml_change.sh` 用 `safe_load_yaml` 读进去注入 `hosts:`。
```
'p2p.douyucdn.cn': 127.0.0.1            # 精确域名，只盖这一个
'+.mcdn.bilivideo.cn': 127.0.0.1        # +. 同时盖顶点域和子域（推荐）
```
**实测：PCDN 家族（`p2p.douyucdn.cn` / `*.mcdn.bilivideo.cn` / `ppio.com` / `onething.com`）→ 127.0.0.1 ✓，而 `www.douyin.com`、`v3-web.douyinvod.com`、`pull-hs-f5-hot.flive.douyincdn.com` 全部回真 IP ✓。**
（注意：`pull-*.flive.douyincdn.com` 曾被当成 PCDN 误黑 —— 那是**直播拉流链路**，见三·九。）

## 三·五、★★ 三个血泪坑（都实际踩过）

### 坑 1：PCDN peer 用「IP 编进子域名」寻址
```
xy116x196x156x111xy.mcdn.bilivideo.cn   -> 203.0.113.1
xy118x212x136x249xy.mcdn.bilivideo.cn   -> 203.0.113.1
```
**规律：`xy<IP，点换成 x>xy.mcdn.bilivideo.cn`。** 所以一个域名后缀通配就能盖住全部 peer，无需逐个追 IP。
在客户端 `ipconfig /displaydns` 里看到这种形态 = **PCDN 调度铁证**，直接拿它当根因证据。

**抖音点播的同类形态**：`120-226-34-134-ne835057.free-lbv6.idouyinvod.com`（标签里是横线版节点 IP `203.0.113.1` + `free-lb<v>` = 免费/边缘 LB）。见到这种「域名里嵌 IP」的形态，**先判变量落在哪一层，再决定能不能封**：
- 变量是**固定父域下的单个标签**（`xy…xy.mcdn.bilivideo.cn`、`<IP>-<id>.free-lbv6.idouyinvod.com`）→ `+.固定父域`（`+.mcdn.bilivideo.cn`、`+.free-lbv6.idouyinvod.com`）可一次盖住 ✓
- 变量落在**父域本身**（版本号进域名：`free-lbv4` / `free-lbv6` …）→ 只能逐个枚举，**别承诺「一句通配全封」** ✗
- 这类域名出现在 DNS 抓包里，同样算 PCDN/边缘调度证据（可报告），但**能不能封是另一件事**。

### 坑 2：`grep -q <子串>` 会让 sed 插入静默跳过
`grep -q "mcdn.bilivideo.cn" /etc/openclash/9.1.yaml` 会被**已存在的 `DOMAIN-SUFFIX,mcdn.bilivideo.cn,REJECT` 规则行**命中 → `||` 短路 → sed 不执行 → **hosts 条目根本没写进去，但每一行输出都显示“成功”**。
→ 必须用**精确 hosts 行**判断：`grep -qF "'+.mcdn.bilivideo.cn': 127.0.0.1"`。同样坑也在 `grep -q '^hosts:'`（运行时 yaml 本来就有 hosts 段）。
→ **改完必须 `sed -n '/^hosts:/,/^dns:/p'` 把实际内容打印出来看，不要看脚本的估计。**

### 坑 3：刷页 / flushdns 都不够，必须完全退出浏览器
Chrome 有**自己的 DNS 缓存**，且播放器把 peer 列表存在内存/localStorage 里：
- `Ctrl+Shift+R` → 旧连接不断，peer 列表还在
- `ipconfig /flushdns` → 清掉一部分（实测切断了京东云那条），但 Chrome 内部缓存与内存里的 peer 列表还在
- **只有完全退出 Chrome 进程（含后台）再重开，才会重新请求 peer 域名——这时才会被拦。**
已建立的 TCP 连接不会自己断，会挂到超时。

### 坑 4：整份 `/proc/net/nf_conntrack` 经 SSH 传两遍会被截断
要算「播放期间每条流跑了多少字节」，需要 t0 / t1 两次快照。**整份 conntrack 动辄几万行，第二次快照会被输出上限吃掉**，于是差值全 0 —— **看起来像「已经修好了」，其实什么都没测到。**
→ 先在路由器上 `grep -a "src=<客户端IP>"` 缩到目标机器，再用 awk 就地把每行压成 `dst:dport bytes`（只输出几十行）：
```sh
grep -a "src=192.0.2.10" /proc/net/nf_conntrack | awk '{dst="";dp="";b="";for(i=1;i<=NF;i++){if(dst==""&&$i~/^dst=/){split($i,a,"=");dst=a[2]}if(dp==""&&$i~/^dport=/){split($i,a,"=");dp=a[2]}if(b==""&&$i~/^bytes=/){split($i,a,"=");b=a[2]}if(dst!=""&&dp!=""&&b!="")break}print dst":"dp" "b}'
```
再在本地对两次输出做差（路由器无 python3）。**分节标记别用 `###`**（会被 shell 吃掉），用 `===T0===` 之类。

## 三·六、验收：怎么判定「修好了」

**判据只有一个：播放期间 PCDN 数据端口（`7826` / `8082`）上的字节增量。**
1. 让用户**真的开始播放**（页面开着不播＝测不到数据通道）。
2. 按坑 4 的方法做 30s 双向采样。
3. 判定：
   - **零字节，或只有「每 10 秒 250 字节」量级 = 纯 TCP 心跳保活 → 不偷带宽，算修好了。**
   - **持续 Mbps 级 = 数据通道还活着 → 没修好。**
4. **交叉确认视频数据来源是正经 CDN**：把下载量最大的远端 IP 与该平台正经域名的解析结果对比（B站 辽宁联通 = `218.60.18.x` / `221.204.56.x`；B站 UOS = `101.69.99.x`）。**不在这些网段、又用非标端口的，才是 PCDN。**

## 三·七、域名层拦不住的那一半（裸 IP peer）—— 交付时要说清楚

**PCDN peer 不只有「IP 编进域名」一种寻址方式，播放地址接口还会直接下发裸 IP。** 裸 IP 不经 DNS，所以：
- `hosts:` 黑洞只能挡住**按域名寻址**的 peer；
- 客户端仍会对裸 IP 建一条 TCP 到 `IP:7826` / `IP:8082`；
- **现象**：DNS 缓存里已经一条 PCDN 域名都没有了，netstat 里却仍有 `*:7826` / `*:8082` 的 ESTABLISHED。

**处理原则：**
- 先用三·六 判定它传不传数据。**心跳不传数据就不必管**，别为了「看起来干净」去动更重的手。
- 要彻底掐掉，唯一办法是在路由器防火墙封 `7826` / `8082` 出站 —— **这是 nftables 改动，必须先问用户**（该用户对路由器防火墙有「严禁改动」硬红线，`fw3 flush` 会冲掉规则直接断网）。
- **交付话术要如实分层**：「域名寻址的 peer 已全黑 + 数据通道零传输；裸 IP 的心跳连接拦不住、但它不传数据；要不要动防火墙你定。」**不要报成 100% 干净。**

### Windows 客户端取证细节
- `ipconfig /displaydns` 是找调度域名最快的路子，但**中文 Windows 的字段名是「记录名称」**，正则需要 `记录名称[\s.·]*[:：]\s*(\S+)`；用 `Record Name` 会一条都匹配不到（表现成「DNS 缓存 0 条」，很容易误判成「没有 PCDN 记录」）。
- **Win11 已移除 `wmic`** → 取进程名/路径用 `Get-Process -Id <pid>`，端口归属用 `Get-NetTCPConnection` 再映射到进程名。
- **浏览器有十几个子进程、PID 每次都变**：永远把 netstat 里的 PID 映射成**进程名**再下结论，否则会把「同一个浏览器」误判成「另一个进程在跑 PCDN」。
- 多行 PowerShell 写成 `.ps1` 用 **UTF-8 BOM + CRLF** 再 scp 过去执行；别手拼 `-EncodedCommand` 的 base64。

## 三·八、★ 「某站也卡，是不是 PCDN？」——电商类自查法 + 两个解析陷阱（2026-10-04）

用户报「XX 也卡」时的正确顺序：**先排除自己的改动 → 再量化 → 最后才怀疑 PCDN**。

1. **先查误伤**：`grep -iE '<站点关键词>' openclash_custom_hosts.list` —— 确认黑洞列表没沾这个站。
2. **查规则走向**：`grep -inE '<域名>' 9.1.yaml`。国内站点应命中 `RULE-SET,ChinaMax,DIRECT`（约 1029 行）或 `GEOIP,CN,DIRECT`（约 1041 行）—— 两者都在 `MATCH,SSRDOG` 兜底**之前**，所以国内域名不会走代理。
3. **量延迟**：路由器上 `ping -c3 <各 CDN 节点 IP>`，全 <50ms 即快。
4. **量吞吐**：抓 conntrack 做**差分**（见陷阱 1）。

### 陷阱 1：conntrack 的 `bytes=` 是**两个独立数字**，不是 `up,down`
一行里有**两个** `bytes=`（原方向 / 回方向），每个都是**单个数字**。
写成 `split(by, ",")` 取 `b[1], b[2]` → 下行恒为 0 → 误报「全是零下载」✗。
正确：按出现顺序取第 1 个和第 2 个 `bytes=` 值。

### 陷阱 2：Clash `/connections` 看不到 DIRECT 的短连接
网页/App 的 HTTP 连接几秒就关，快照往往只剩推送类长连接。
**别用连接表快照判断「有没有走代理」** —— 改用规则命中 + 节点延迟实测。

**量化后的样子更误导**：每 4 秒采一次、连采 6 分钟，某台手机在快照里**只有 2 条连接**（苹果推送 + 邮件），而同一时段的 DNS 抓包里有 **216 次查询**、其中一大批正是它要看的那款 App 的点播/直播域名 —— **快照里的「0 条」是采样间隙造成的假象，不等于「没用这个 App」**。判断 App 卡/停/是否在偷传，一律用 conntrack（陷阱 1 的差分法）或 tcpdump 级抓包，不要拿周期性 API 快照下结论。

### 电商类结论（京东，2026-10-04 实测）
- 京东系域名**全部 DIRECT**（ChinaMax 命中），PCDN 黑洞**一条不沾** ✓
- 图片 CDN：`img14.360buyimg.com` → CNAME `sz-spring-img.volcgtm.com`（火山引擎/深圳）→ `42.59.0.137`，实测 **1.9ms**；`www.jd.com` → `203.0.113.1`（辽宁本地）**1.7ms** ✓
- 手机端京东：**0 个 PCDN 端口（7826/8082）连接**、无异常上传 → **电商 App 不做 PCDN**
- 真因是**支付环节**（境外万事达卡不支持国补商品），与网络无关 ✗

## 三·九、★★ 别把「直播拉流链路」当 PCDN（2026-10-04 踩过，用户报“抖音又卡了”）

判据只看**域名语义**，**不要**看“能不能解析出真 IP”（真 IP 恰恰说明它是正经 CDN ✗）：

| 名字形态 | 性质 | 该不该黑 |
|---|---|---|
| `p2p-*` / `p2pchunk-*` / `*-p2p` / `peercdn` / `ppio` / `onething` / `xycdn` | PCDN/P2P | ✓ 该黑 |
| `pull-rtmp-*` / `push-rtmp-*` / `*.flive.*`（FLV live） / `pull-flv-*` | **直播推拉流** | ✗ **绝对不能黑** |
| `pull-hs-*` / 普通 `*.douyinvod.*` | 常规 CDN 播放 | ✗ 不黑 |

**踩法**：`pull-hs-f5-hot.flive.douyincdn.com` 解析出真 IP（203.0.113.1）就被当成“能拦的 PCDN”加进黑洞 ✗ —— 但 `flive` = **FLV 直播**、`pull-` = **拉流** ✗。同理 `pull-rtmp-l11.ixigua.com` / `push-rtmp-l1.ixigua.com` = 抖音/西瓜直播推拉流 ✗。
**症状**：直播黑屏/无限转圈，短视频也可能卡（App 会去试直播域名）✗。

**回滚方法**（不重启服务、不动 nftables）：
```sh
# ① 备份
cp /etc/openclash/custom/openclash_custom_hosts.list /root/bk/
cp /etc/openclash/9.1.yaml /root/bk/
# ② 两边同时删（custom 列表 + 运行时 yaml 的 hosts 段，缺一不可）
for d in flive.douyincdn.com pull-rtmp-l11.ixigua.com push-rtmp-l1.ixigua.com; do
  grep -v "$d" /etc/openclash/custom/openclash_custom_hosts.list > /tmp/a && mv /tmp/a /etc/openclash/custom/openclash_custom_hosts.list
  grep -v "$d" /etc/openclash/9.1.yaml > /tmp/b && mv /tmp/b /etc/openclash/9.1.yaml
done
# ③ 热重载（HTTP 204 = 成功），比 restart 安全得多
curl -s -X PUT -H 'Authorization: Bearer <secret>' -H 'Content-Type: application/json' \
  -d '{"path":"/etc/openclash/9.1.yaml"}' 'http://127.0.0.1:9090/configs?force=true' -w 'HTTP=%{http_code}\n'
# ④ 双向验证：被删的应回真 IP；真 PCDN 应仍 127.0.0.1
```

**教训**：加黑洞前逐条看**域名语义**；加完要同时验证「目标生效」**和**「无关播放链路未被误伤」。

## 三·十、★ 抖音（iOS）PCDN 实测：有 PCDN 行为，但封不住、也不值得封（2026-10-04）

**抓取方法**（iOS 没有 `ipconfig /displaydns`，全靠路由器）：
```sh
# ① DNS 查询（能看到 App 查了什么域名 + CNAME 链）
tcpdump -i any -n -l -s0 'udp port 53 and host <手机IP>' > /tmp/dy_dns.log 2>&1 &
# ② 每 5s 快照 Clash /connections + conntrack 做差分（cumulative bytes → 速率）
#    坑：conntrack 一行有两个 bytes=，按出现顺序取第 1、2 个（其余字段同样）
# ③ 归属判定：`curl -x socks5h://127.0.0.1:7899 -X POST -d '[...]' http://ip-api.com/batch`
```

**抖音系域名归属（实测）**：
| 域名 | 归属 | 用途 |
|---|---|---|
| `*.vegslb.com`（随机长串子域） | 北京火山引擎科技（京ICP备20018813号-136，NS=BYTEDNS） | 火山 LB / **PCDN 调度** |
| `*.rtcxyz.com`（`signal-t1-v6-az1-01`） | **抖音视界有限公司**（京ICP备19059916号-99，NS=volc-dns） | 火山引擎 **RTC 信令**（连麦/低延迟直播） |
| `*.queniurc.com` / `*.queniuuf.com` | 浙江雀牛网络科技（雀牛云CDN） | 抖音 CDN 的 **CNAME 目标**（在 `p3-webcast.douyinpic.com` 链里）✗ 不能封 |

**实测（iPhone 刷抖音 90 秒）**：上传 1.11MB / 下载 9.77MB（11.4%）；视频流走 **UDP 8563-8710 / 96xx** 到沈阳·济南·石家庄节点；另有 6 条**家宽 IP + 随机高位端口**（35002/35009/35013/53861，江苏/福建/天津/甘肃/**广东移动家宽**）的连接尝试 —— **全部 0 字节**。

**结论**：
- 抖音**确有 PCDN 行为**（向家宽 IP 发起 peer 连接）✓
- 但对 peer 的**上传 ≈ 0**（NAT 打洞不成交）→ 没有“偷上传”问题 ✓
- **PCDN 对端是裸 IP，DNS 黑洞无效** ✗（不像 B站 `mcdn.bilivideo.cn` 有域名可封）；要拦只能封端口 = 动 nftables ✗
- 能封的域名（`vegslb.com`/`rtcxyz.com`）**同时承载抖音正常功能**（RTC 连麦/低延迟直播）→ 封了必然坏 ✗

**通用判据**：先量「上传/下载比」再决定封不封 —— peer 通道 0 字节、总上传比 <15% 就是**没在偷上传**，别为省流量去动播放链路 ✗。

## 三·十一、★★ 文件改了 ≠ 生效了 —— 每次改配置都要验证「运行时已生效」

热重载的**返回码是唯一生效证据**：
- **204 = 已生效**；**401 = secret 不对 → 文件已改，但运行中的配置仍全是旧的**（症状极像「我的修改没用」，会把人引到错误结论 ✗）；其他非 204 一律当**没生效**处理。
- 所以删完条目后，**必须再解析一次被撤域名**：`nslookup <域名> 192.0.2.10` 回真 IP / `198.18.x` 才算真撤掉；**仍回 `127.0.0.1` 就是重载没落地**，不要去看文件确认「已经删了」。

**secret 取自运行时配置本身**（`/etc/openclash/9.1.yaml` 里的 `secret:`，不是 `config.yaml`，别去别处找），在路由器本地取进变量、**不打印内容**：
```sh
SEC=$(grep -h -m1 -E '^[[:space:]]*secret:' /etc/openclash/9.1.yaml | head -1 \
      | sed 's/.*secret:[[:space:]]*//' | tr -d "\"' ")
curl -s -o /dev/null -w 'HTTP=%{http_code}\n' -X PUT -H "Authorization: Bearer $SEC" \
  -H 'Content-Type: application/json' -d '{"path":"/etc/openclash/9.1.yaml"}' \
  'http://127.0.0.1:9090/configs?force=true'
```

**远程执行三件套**：路由器是 BusyBox，**别把脚本塞进 `ssh "..."` 内联**（引号嵌套会炸成 `unexpected EOF`，且报错发生在本地、看不到失败原因）。一律 `write_file` → `scp -P 2222` → `ssh "sh /tmp/x.sh"`。要分析 Clash API 的 JSON：在路由器上 `curl ... > /tmp/conns.json` 再 `scp` 回容器用 Python 处理（路由器没有 python3，secret 也就不必离开那台机器）。

### 复发问题的第一动作：撤掉自己最后加的那一条
同一个服务「又卡了」时，**先查自己最后一次动过什么**（`grep -inE '<关键词>' openclash_custom_hosts.list` + 运行时 yaml 各查一遍），把**单条**撤掉再让用户重试 —— 单条回滚零成本（若三·十 已量出 peer 上传 ≈ 0，封它的收益本来就是 0）。
撤完要**如实说因果未确认**：「已撤 X。它是不是真因，要等你重试才知道」—— 别把「我改回去了」讲成「我修好了」✗（该用户明确讨厌这种假结论）。
撤完还要报**黑洞总条数**（`grep -cvE '^\s*(#|$)'`），条数是两侧一致性的自检。

### 自证清白的最快证据：DNS 答案里 `127.0.0.1` 的条数
用户报「又卡了」而你最近刚动过黑洞清单时，**先给一个确定的结论，再谈别的**：抓一段 DNS（`tcpdump -i any -n -l -s0 'udp port 53'`）+ 同期 Clash 快照，数**被解析成 `127.0.0.1` / `0.0.0.0` 的答案条数**。
- **0 条 = 那一刻黑洞清单完全没参与** → 可以直接排除自己的改动 ✓（这条证据几分钟就能拿到，别让用户等一整套排查）
- 顺带白拿三件事：卡的那个 App 到底在查哪些域名（点播 / 直播拉流 / RTC 信令 / API 各是哪类）、有没有被调度到外地节点、有没有「域名里嵌 IP」的边缘节点线索

**交付结构（该用户认这个形状）**：① 我的改动是否涉及（自证或认账，附证据条数）② 有没有该直连的走了代理 ③ 域名解析是否正常、是否本地节点 ④ 有没有 PCDN/边缘节点线索 ⑤ **这轮抓包有没有真的抓到你用它的那一刻** —— 没抓到就明说「这轮没数据」，**绝不要把「没测到」讲成「没问题」** ✗

## 三·十二、★★★ 「视频加载慢」常是 CDN 调度跟错了 DNS 出口（不是代理、不是黑洞）

用户说**「加载慢 / 一个视频得过一会才能加载出来」**时的判据与修法。

### 判据
- 国内 CDN（抖音/字节最明显）**按「解析器的 IP 归属」选节点**，不按客户端真实位置。
- **延迟不是判据** ✗：用户说「加载慢」= 吞吐/首段慢。视频是**大量短连接分段**，每段都要重走 TCP 慢启动 → **节点 RTT 被逐段放大**。所以量的是**节点 RTT**（实测本地 `2.5~9ms` vs 外地 `25~34ms`，差 3~10 倍）。
- 抖音域名的 CNAME 链会落到**第三方 CDN 父域**：`jomodns.com`（= 又拍/同鸣）、`bytefcdn.com`、`volcfcdndvs.com`、`bdydns.com`、`ctlcdn.cn` → **光靠 `geosite:cn` 可能盖不住，必须显式列**。
- 字节系 CDN 已 **IPv6 优先**：运营商 DNS 对抖音返回的几乎全是**本地 IPv6 节点**（`2408:8730:500:18:...` = 联通辽宁）。本环境 `br-lan.disable_ipv6=1` + `dhcp.@dnsmasq[0].filter_aaaa=1` 把 v6 全掐了 → 只能退回 IPv4 → 而 OpenClash 上游 DNS 是阿里/114（不在本省）→ CDN 把你调度到 **上海/山东/浙江** ✗。

### 修法（只改 DNS 调度，不碰 nftables）
1. `openclash_custom_domain_dns_policy.list` 就是 mihomo 的 `nameserver-policy` 来源（文件里自带注释示例 `#"geosite:cn": [...]`）。
2. 内容（键写纯域名时**同时覆盖其子域**）：
```
"geosite:cn": [203.0.113.1, 203.0.113.1]
"geosite:bytedance": [203.0.113.1, 203.0.113.1]
"douyinvod.com" / "douyincdn.com" / "douyinliving.com" / "douyinstatic.com" / "douyinpic.com"
"bytefcdn.com" / "volcfcdndvs.com" / "jomodns.com" / "bdydns.com" / "ixigua.com" / "snssdk.com" / "amemv.com" → 同上
```
3. **只列运营商 DNS，绝不掺公共 DNS** ✗ —— nameserver-policy 的多台服务器是**并发查询取最快**，掺进 `203.0.113.1`/`203.0.113.1` 会因应答更快而胜出，调度又回到外地。
4. 同一份内容还要**同步进运行时 `/etc/openclash/9.1.yaml` 的 `dns:` 段**（新增 `nameserver-policy:` 块）—— 自定义 `.list` 只在 OpenClash 重启时才重新生成，热生效必须双写（与 `hosts:` 同一个模式）。

### 坑（都实际踩过）
- **追加前先确认末行有换行**：OpenClash 自带策略文件**末行是无换行的注释** → `cat >>` 会把新条目拼到注释行尾 → **整条被当注释忽略**，持久化文件看着改好了，重启后策略凭空消失 ✗。追加后 `tail -3` 看一眼。
- **BusyBox `nslookup` 会同时打 A 和 AAAA**：`awk '/^Address/{a=$NF} END{print a}'` 取到的是**最后一条 = AAAA** → 于是「运营商 DNS 只给 IPv6」这种假结论就出来了 ✗。要比 IPv4 就**只抓 `Address N: <v4>`**，或把原始输出落文件、scp 回容器用 Python 解析（最省心）。
- 把 awk/grep 单行塞进「Python 生成的 shell 脚本」里仍会炸（`awk: Unexpected token`）→ **原始输出落文件 + 本地解析**，别在路由器上做复杂字段抽取。
- `mihomo -t -f /etc/openclash/9.1.yaml -d /etc/openclash` 可能报 `path is not subpath of home directory or SAFE_PATHS: /usr/share/openclash/ui` 并 FAILED —— 这是 OpenClash 的 external-ui 路径越界，**不是 YAML 有错** ✗。别据此回滚；真正的生效证据是热重载 **HTTP 204**。

### 验证（两层，都要做）
```sh
# ① 直接问内核它现在解析出什么
SEC=$(grep -h -m1 -E '^[[:space:]]*secret:' /etc/openclash/9.1.yaml | head -1 | sed 's/.*secret:[[:space:]]*//' | tr -d "\"' ")
curl -s -H "Authorization: Bearer $SEC" "http://127.0.0.1:9090/dns/query?name=<域名>&type=A"
# ② 节点 RTT 对比（本地 vs 外地）
ping -c 3 <解析出的IP>
```
判据：CNAME 目标应从外地换成**本地网段**（辽宁联通 = `218.60.x` / `218.24.x` / `42.4.x`），RTT 落到个位数 ms。

**副作用要主动交代**：`geosite:cn` 全覆盖 = 全家国内域名改走运营商 DNS（B站/爱奇艺/腾讯视频/微信 一起受益 ✓），**墙外流量不受影响**（仍走原代理 + fallback ✓）。回滚 = 撤策略行 + 热重载 + 复核解析。

**让用户重试前必须交代「先把 App 杀掉再重开」**：App 会缓存旧节点 IP / DNS 结果，不重开根本看不出效果 ✗。

## 四、落地步骤
1. 备份 `openclash_custom_hosts.list` + `openclash_custom_fake_filter.list` + `openclash_custom_rules.list` + `/etc/openclash/9.1.yaml` 到 `/root/oc-pcdn3-<TS>/`。
2. 把黑洞条目追加到 `openclash_custom_hosts.list`（**2 空格缩进、`'域': 127.0.0.1`，必须是合法 YAML**）。
3. **同步注入运行时**（OpenClash 只在重启时重新生成，热生效必须手改）：
   ```
   sed -i "/^hosts:/r /tmp/hosts_blk.txt" /etc/openclash/9.1.yaml
   ```
   坑：运行时 yaml **本来就已有 `hosts:` 段**（只有 `localhost.localhost`），别用 `grep -q '^hosts:'` 判断后跳过嵌入。
4. 热重载（**不要 restart**，会断网）：
   ```
   curl -X PUT -H "Authorization: Bearer <secret>" -d '{"path":"/etc/openclash/9.1.yaml"}' 'http://127.0.0.1:9090/configs?force=true'
   ```
   204 = 成功。
5. 验证：抽样 `nslookup <pcdn域名> 127.0.0.1` 应为 `127.0.0.1`；对照 `douyin.com`/`aweme.snssdk.com`/`www.baidu.com` 应回真 IP；再跑 `curl -x http://127.0.0.1:7890 https://www.google.com/generate_204` = 204 确认没断网。
6. **把改后的 yaml 拉回本地用 Python `yaml.safe_load` 跑一遍**——否则写坏 YAML 会在下次重启时才爆。
7. **让用户刷新/重开播放页**：已建立的 PCDN 连接不会自己断。

## 五、实环境记录（2026-10-04）
- `pve-administration` 家族，路由器 iStoreOS 192.0.2.10（SSH 2222），内核心 alpha-9f053c4，`secret` 在 `/etc/openclash/9.1.yaml`。
- **当前生效 52 条，全部是「纯 P2P/PCDN 命名」的域名**：通用众包 PCDN 厂商（ppio/onething/onethingpcs/pkoplink/p2cdn/xycdn/xycloud/xyp2p/yfcdn/yfp2p/yfcloud/uhabo/bsccdn/peercdn/cdnbye/nexusedgeio/p2ptun/p2pvod/p2p-ali/v-p2p/smtcdns…）+ 平台自家 P2P（`p2p*.douyucdn.cn`、`p2pchunk-*.douyucdn.cn`、`dyp2p-*.douyucdn.cn`、`stun*.douyucdn.cn`、`p2p.huya.com`）。**字节自家条目已全部撤除** —— 唯一一条 `p2p-v.byteoversea.com` 是海外版、国内播放用不到，实测上传 0 字节即收益为 0，已按上面「复发先撤自己最后一条」的规则移除。
- **已撤回，别再照抄旧清单**：`+.flive.douyincdn.com`、`pull-rtmp-l11.ixigua.com`、`push-rtmp-l1.ixigua.com`、`+.wxlivecdn.com`。名字含 `flive`/`rtmp`/`live` 的是**播放/推拉流链路**，误黑直接把直播和短视频打黑屏。
- **覆盖真相（对用户必须如实分层）**：这份清单拦的是**第三方众包 PCDN 厂商**；**抖音自家（字节）的 PCDN 基本没被覆盖**（只有海外版 `p2p-v.byteoversea.com` 一条）。要封抖音自家 PCDN，只能在用户真刷抖音时抓它实际连的域名、再按语义分类，**不能照搬别人的清单**。
- **机制已就绪**：fake-ip-filter 里已有 13 条字节系（`+.douyin.com`/`+.douyincdn.com`/`+.douyinvod.com`/`+.douyinstatic.com`/`+.douyinpic.com`/`+.amemv.com`/`+.snssdk.com`/`+.isnssdk.com`/`+.pstatp.com`/`+.ipstatp.com`/`+.ixigua.com`）→ 抖音多数域名已回真实 IP → **`hosts:` 黑洞对抖音能直接生效**，不必再折腾 bypass。
- B站 侧另加 3 条 REJECT：`mcdn.bilivideo.com` / `mcdn.bilivideo.cn` / `szbdyd.com`，且把 `*.mcdn.bilivideo.cn` 从 fake-ip-filter 里摘掉。
- 字节系 24 条 fake-ip-filter 条目**保留**（防抖音被 `RuleSet(TikTok)` 抓去日本）；实测运行时 `DOMAIN-SUFFIX,douyin.com,DIRECT`(828 行) 在 `RULE-SET,TikTok`(967 行) 之前，理论上已冗余，但不要在不看抖音的时段拿它做实验。

## 六、术语
- fake-ip-filter 条目命中 → 返回真 IP → 绕过 Clash。
- `Redir` vs fake-ip 是两个层面，不冲突。
- 内网速度测试用 Speedtest-X，不走宽出口。
- 路由器**无 python3**；需解析时 `ssh ... cat > /tmp/x` 拉回本地用 Python 处理。
