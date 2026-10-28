---
name: selfhosted-service-ops
description: "Use when 部署/备份/核对自建服务（密码库类）。"
---

# 自建服务的部署、备份与凭据核对

家里 PVE 上跑着一批自建服务，新增一个就是「建 CT → Docker → Caddy → 导航页 → 备份/更新」一条流水线。**一次配完，不要分多轮问**（the user explicitly讨厌反复操作、讨厌重复提供密码）。

发布到公网（Caddy 模板、DNAT、DDNS、证书）、PVE/LXC 底层分别见用户自有技能 `home-public-services` / `pve-administration`。**本技能只管应用层**：容器运维、数据备份、凭据核对。

## 服务台账

| 服务 | 位置 | 访问 | 备注 |
|---|---|---|---|
| Stirling-PDF | PVE CT <ID> / `192.0.2.10:8080` | `https://pdf.example.com:18443` | 详见 `stirling-pdf` |
| Vaultwarden 密码库 | PVE CT <ID> / `192.0.2.10:8080` | `https://pass.example.com:18443` | 1核/1G/6G，实测 16 MB |
| nav 入口站 | CT <ID> `/var/www/nav` | `https://example.com:18443` | 详见 `nav-monitor` |

## 部署流程（app 层）

1. **建 CT**：`--features nesting=1,keyctl=1` 是 Docker 在 LXC 里跑的前提，漏了起不来。DHCP 出 IP 要等 15–30 秒，**循环重试别只查一次**。小服务 1 核/1G/6G 足够。
2. **起容器**：数据挂宿主 `/opt/<服务>/data`（容器重建不丢数据），`--restart unless-stopped`，内存上限按实测收紧。
3. **Caddy 块**：带 WebSocket/SSE 的服务（Vaultwarden 的 `/notifications`、noVNC 推流）必须加 `flush_interval -1`，且**写在内 `reverse_proxy` 子指令里**——放 site 块顶层会 `unrecognized directive` 直接打挂全部站点。应用侧 `DOMAIN` 必须等于用户实际访问地址**含端口**。
   **反代「设备自带后台」（路由器/AP/摄像头/NAS 控制台）和反代普通 Web 应用不是一回事**：上游优先写 `http://`（这类设备 https 多为自签，老型号可能根本没有 https，实测锐捷 EAP602 的 https 直接 `000`），全走 http 就不用 `tls_insecure_skip_verify`；带实时状态推送的后台（eWeb、流量图）一定要 `flush_interval -1`，否则页面一直转圈；`header_up Host {http.request.host}` 对这类设备通常无害。**但反代后必须在真浏览器里登录一次**，确认登录后的跳转 URL 里的是**域名而不是内网 IP**——设备若在重定向里写死内网 IP，用户点完就被踢回内网，反代等于白做。
   **设备登录页常有 0×0 隐藏诱饵输入框**：同名 `input` 出现两个，其中一个是 `getBoundingClientRect().width === 0` 的防自动填充陷阱，`querySelector` 会选中它，填进去**永远登录失败且页面不报错**，看起来完全像「密码不对」。填之前必须用 `width > 0` 过滤出可见框。同一设备的另一型号可能只需密码（用户名固定 admin）、老型号要用户名+密码两栏，**别把同一个密码在两代产品上的行为当成同一个结论**。
   **验证“能登录”之前不要把结论下成“密码错”** —— 先排除选错框、再排除固件代际差异，最后才怀疑密码；设备多次失败会锁号。
   **拿设备清单/各台对应位置时不要猜**：列表页常把「设备」与「位置名」拆成**两张独立 table 各 N 行**（不是同一行的多个 td），按**行序 index 配对**，再用型号交叉验证（室外型对院子、室内吸顶对楼层）。行数不一致 = 有过滤条件没清，别硬配。
   **加新子域不用碰 DDNS**：`*.example.com` 是泛解析，`dig +short 新子域.example.com A` 有结果就行（详见 `home-public-services`）。
4. **导航页卡片** + `SERVICES` 探活（注意那张表是**多空格对齐**格式，用 patch 工具按真实行改，单空格 `str.replace` 会静默不匹配）。
   **一个服务带一堆同级子入口时（AC+4 台 AP、一条业务的多个面板）别铺 N 张卡把页面刷爆**，做成「一张卡 + 弹窗」：卡片 `data-svc` 填主设备 key，弹窗里逐个列子入口。三个易漏点：① collector `SERVICES` 里**每个子入口都要一条**，否则弹窗拿不到独立状态；② `id` 全局唯一，卡与弹窗不能都叫 `sv-ac`，子入口用独立前缀（`m-ac` / `m-ap1`）；③ 前端渲染循环里要给子入口状态点补一行 `const m = $('m-'+k); if (m) m.className = 'dot ' + (v.up ? 'on' : 'off');` —— **漏了就是卡片绿、弹窗全灰**。
5. **备份 + 更新 timer**（见下）。
6. **交付时报实测值**：`docker stats --no-stream` 的内存/CPU，不报标称规格。

## 凭据核对（用户说「密码不对，你改了吧」时）

**先查文件，再开口。** 顺序固定，不要跳：

1. `stat -c %y <凭据文件>` 看修改时间 —— 判断是否本次真动过。
2. 用 `hmac.compare_digest` 逐个比对用户报的值（含长度变体、大小写变体）。
3. 独立记下存储值的**长度与首字符**。

**长度都和用户记的对不上，就说明那从来不是同一个密码，不是本次改坏的。** 把 mtime + 长度 + 首字符当证据摆出来：既不含糊认错，也不长篇辩解；然后按用户要的值改掉，并**实测登录**（POST 登录端点看 302、再带 cookie 访问首页看 200），最后告诉用户能用了。

改凭据后记得重启读该文件的服务（很多认证器是**启动时读一次**，改文件不重启不生效）。

凭据位置统一记在一处：`~/.hermes/secrets/ACCESS-NOTES.md`（600）。生成随机值：`openssl rand -base64 24 | tr -d '/+='`。

## 用户看到「密码已泄露 N 次」时（密码库做安全体检）

**先定性：这不是自建服务被黑。** Bitwarden/Vaultwarden 的「暴露的密码 / Exposed Passwords」报告查的是 **HIBP 公开泄露库**（收录上亿条已外泄口令），走 **k-anonymity**：客户端把口令做 SHA-1，**只把前 5 位**发给 `api.pwnedpasswords.com`，取回该前缀下的全部后缀在**本地**比对 —— 完整口令与完整哈希都不出门。所以它既是零知识加密下唯一可行的云端查询方式，也是**安全功能在正常工作**，不是漏洞。

**先自己实测再解释给用户**（只发前 5 位，安全；被墙走本地代理）：
```python
import hashlib, urllib.request
h = hashlib.sha1(pw.encode()).hexdigest().upper()
req = urllib.request.Request(f"https://api.pwnedpasswords.com/range/{h[:5]}",
                             headers={"User-Agent": "curl"})
txt = urllib.request.urlopen(req, proxies={"https": "http://127.0.0.1:7899"}).read().decode()
count = next((int(l.split(':')[1]) for l in txt.splitlines() if l.startswith(h[5:])), 0)
```

**报告里的具体数字能反推是哪个口令**：拿用户常用的几个候选逐个实测，**命中同一个数（例如 6,421,042）就锁定那个口令**，比空口解释有说服力。数量级含义：千万~亿级 = `123456`/`password` 这类烂大街口令；几百次 = 弱但不致命；**0 次 = 干净**。

**交付口径**：① 明确说「不是你服务器的问题，是口令本身在公开泄露库里出现过」；② 给实测对照表（含用户自己正在用的那个）；③ 强调**泄露过的口令换掉 + 开 2FA**，因为「口令泄露后唯一还挡得住的只有第二因子」；④ 别顺势推销让别人给 AI 读密码库权限 —— 零知识加密的价值就在于 agent 读不到。

## 数据备份（SQLite / 文件服务）

- **WAL 模式必须三件套**：`db.sqlite3` + `-wal` + `-shm` 一起拿。只拷主库会丢最近写入。
- **容器里通常没有 `sqlite3` 命令**，别指望 `.backup`，直接 `cat` 出来再校验。
- **`shutil.make_archive` 的格式名是 `gztar`**；写 `gzip` 抛 `ValueError: unknown archive format 'gzip'`。
- **备份要验真**：解包后连库跑 `pragma integrity_check` + 数表数，别只看文件大小（几 KB 也可能是空壳）。
- 用 systemd `oneshot` + `timer`（`Persistent=true`、`RandomizedDelaySec`），纯脚本 0 token。密码库这类有安全公告的服务另配一个**每周拉新镜像重建容器**的更新 timer（数据在 volume 里不受影响）。

现成脚本：`scripts/sqlite_service_backup.py`，改顶部常量即可复用到其他服务。

## 容器坑

1. **环境变量运行中改不了**：`docker run -e` 的变量无法 modify，改注册开关这类只能 `docker rm -f` + 用**同样的 volume** 重建（数据不丢）。**测试期先开放注册，用户注册完立刻关掉并确认。**
   **确认别读 `/api/config`** —— `SIGNUPS_ALLOWED=false` 生效后它回的 `disable-user-registration` 仍可能是 `False`（语义不是你以为的那样），看着像没关掉。可靠判据两条：① 登录页上 `Create account` 链接消失（前端路由仍能渲染 `#/signup` 表单，那不代表服务端放行）；② **用假邮箱提交一次注册后 `users` 表行数没涨**，这才算真关了。
2. **空目录挂载会遮住镜像自带文件**（典型：tesseract 的 `tessdata` 语言包与 `configs/`），且**替换目录后必须 `docker restart`**，否则挂载仍指向旧 inode。要自定义就先用 `docker create` + `docker cp` 把镜像里的整体提取出来再加自己的。
3. **验证「能不能注册/登录」不要猜 API 端点**：直接开网页看有没有 `Create account` 之类入口，比猜 `/api/accounts/register` 快得多（猜错拿到的是 404 的 HTML 页面，极易误判成「服务坏了」）。
