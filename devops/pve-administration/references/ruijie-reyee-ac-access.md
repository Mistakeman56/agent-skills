# 锐捷 Reyee AC/AP 访问与无线体检（EG210G-P / EAP262 / EAP602）

用户家无线栈：AC `EG210G-P-E` @192.0.2.10，AP×4 = 一楼/二楼/三楼 `EAP262(E)` + 院子 `EAP602`。
**无线/漫游配置全在 AC 上**，AP 是被管理的（Working Mode: AP）。

## 1. 拿不到 SSH 时的登录路径

锐捷 Reyee **SSH/Telnet 默认全关**（22/23/2222/20000+ 全闭），web 在 80/443。
只能走 eWeb：`https://192.0.2.10/cgi-bin/luci/`

### 登录页只要密码（用户名写死 admin）

密码是**前端 AES 加密**后 POST 到 `/cgi-bin/luci/api/auth`：

```js
GibberishAES.enc(passwordEl.value, "<32位十六进制key>")
// => base64("Salted__" + 8字节随机salt + AES-CBC密文)
```

**复现（openssl）：必须带 `-md md5`**

```bash
printf '%s' "$PW" | openssl enc -aes-256-cbc -a -A -salt -md md5 -pass pass:$KEY
```

> ⚠️ 两个坑，踩了就报 `Auth key is invalid`：
> 1. **不加 `-md md5`** → openssl 现代默认 SHA-256 派生，key 对不上。
>    GibberishAES 用的是 MD5-EVP_BytesToKey（256位=AES-256，key 32B + iv 16B）。
> 2. **AES key 每次失败尝试后轮换**。key 只能从**当前**登录页 HTML 里 regex 出来，写死必失败：
>    `GibberishAES\.enc\([^)]*?,\s*"([0-9a-f]{16,64})"`
>    失败响应长这样：`{"msg":"Auth key is invalid.","reload":true}`

请求体：
```json
{"method":"login","params":{"username":"admin","time":"<unix秒>","encry":true,"pwd":"<AES密文>"}}
```
成功：`{"code":0,"data":{"token":"…","sn":"ZARC0KT007974","sid":"…"},"error":null}`

### ⚠️ 抓登录页前必须清 cookie

带会话 cookie 请求 `/cgi-bin/luci/` 会返回**已登录界面**，里面没有 `GibberishAES.enc` → key 提取为 None。
所以 `_current_key()` 里先 `rm cookie jar` 再抓。

## 2. 浏览器驱动（推荐：避开 API 签名）

eWeb 是 Vue SPA + webpack。**API 每个请求带签名头**，很难复现：
```js
headers:{"Content-Accept": MD5("Web@Rj$2020!" + serialize(data)),
         "Contents-Accept": MD5("Web@Rj$2020!" + JSON.stringify(data))}
// 密钥常量 "Web@Rj$2020!"；MD5 模块 vendor.js 里 webpack id "L6bb"（确认是标准 MD5）
// 会话也可能走 URL query：e = window.BASE_URI + e; r && (e = e + "?auth=" + window.sid)
```
实测 `?auth=<sid>` 能过认证（错误从 `auth is not passed` 变成 `INVALID DATA`），但请求体仍被拒。
`;stok=<token>/api/cmd` 路径返回页面壳，不是 API。**别再花时间逆签名，直接用浏览器读 UI。**

### 让 browser_vault_fill 认得出锐捷登录页 ★

锐捷密码框是裸 `input#password.loginPass`（无 `<form>`、无用户名框）。
保险箱分类器 `agent/vault_login_classifier.py` 只排除 `autocomplete` 为 `new-password`/`one-time-code` 的，
但实测**必须先给字段加上 `autocomplete="current-password"`** 才注入成功：

```js
document.querySelector('#password').setAttribute('autocomplete','current-password')
```
然后 `browser_vault_fill(handle)` → `filled_fields:1` → 点 `#login`。

其他坑：
- 自签名证书会拦一次，先点 `#details-button` 再点 `#proceed-link`。
- 登录页有个 `I have read and agreed` 按钮（class `read-agreement`），先点它否则登录钮不可用。
- 提交成功后 URL 变 `…/cgi-bin/luci/;stok=<token>/admin/home_overview`，`stok` 即会话令牌。

## 3. 关键页面路由（点菜单文字，不是 a[href]）

| 页面 | 路由 |
|---|---|
| 概览 | `admin/home_overview` |
| 物理拓扑（全设备+SN） | `admin/network/topo_map` |
| 设备清单（型号/固件/IP） | `admin/device` |
| 无线优化 WIO | `admin/home_overview/wio`（漫游在 `?tab=3`） |
| Radio Setting | `admin/home_overview/wifi_advanced` |
| LAN Ports（VLAN，非速率） | `admin/home_overview/wifi_wirelan` |
| 单台 AP 详情 | `admin/alone/network/network_wan?sn=<SN>` |

AP 详情页能看到：SSID/频段/频道/Tx Power、客户端清单（信号 + **协商速率**）、Ethernet status。

## 4. 本户实测配置与体检结论（2026-10）

**无线参数**：Country=China(CN)；**2.4G 20MHz**；**5G 80MHz**（未用160）；Multicast=Auto；Client Count Limit=开；
断开 RSSI 阈值 -85/-65dBm。

**802.11k/v 漫游优化：已启用**，但**上次环境扫描 = 2025-12-22**（近 10 个月前的拓扑快照）——
页面自带警告「拓扑变了请重新扫描」。

**固件**：AC `ReyeeOS 2.340.0.2418`（比 AP 还旧）；3×EAP262(E) `2.380.0.2328`（可升级）；
院子 `EAP602` = `AP_3.0(1)B2P20,Release(07180312)`（完全是另一个老固件线）。

**★ 根因（“2000M 发挥不出来”）**：
**★ 频道规划（必须逐台读全，别只看一台）**：

| AP | 2.4G | 5G | 5G客户端/总 |
|---|---|---|---|
| 一楼 .117 | ch12 | ch36 | 0/4 |
| 二楼 .142 | ch2 | ch36 | 2/3 |
| 三楼 .174 | ch7 | ch36 | 5/9 |
| 院子 .169 | EAP602 老固件，界面不同 | — | 1/1 |

- **2.4G = `12/2/7` → 有效的非重叠三信道规划，不是故障。** WIO 有意避开邻居占用的 1/6/11。
- **5G = 三台全 `ch36` @80MHz ← 真问题**：同频抢空口，三楼（9 台客户端 / 5 台 5G）受影响最直接。
- ⚠️ **教训：只读一台 AP 就宣布「四台全挤 ch12」被用户当场打回。** 判断频道规划必须逐台读全再开口。
- ⚠️ **别把「PC 跑不满 2000M」往无线头上扣** —— 用户 PC 走 LAN 口（eth2 2500M），那条链路与无线无关。
- 无线侧实测抖动：手机 `min 2.4 / avg 39 / max 112 ms`、iPad `17/80/128 ms`，
  而有线设备 `0.18/0.31/0.38 ms` —— **`min` 小而 `avg` 爆 = 抢空口**，与「视频一卡一卡」严格对应。

**改动顺序**（① 零风险，② ③ 低风险可回滚，④ 会重启无线，须先备份）：
① 重跑 WLAN 环境扫描 ② 5G 优先/频段引导 ③ 2.4G 错开 1/6/11 ④ 升固件

⚠️ `Wireless Intelligent Optimization`（深优化/680s）会**自动改频道和功率并中断无线**，必须用户明确批准后执行。

## 5. WIO 优化的正确入口：Advanced Settings ★

不要盲跑 WIO。`WLAN Optimization → Network Optimization → Advanced Settings` 里有全部射频旋钮：

```
Scan time | Roaming Sensitivity | Transmit Power
2.4G: Channel Width + Selected channels (CH.1–CH.13)
5G  : Channel Width + Selected channels (CH.36/40/44/48/52(Radar)/56/…/149/153/157/161/165)
```

关键约束（实测有用）：
- 说明里明写「仅支持 5GHz 的 20/40/80MHz 参与优化」。
- **80MHz 下 5G 只有 `36-48` 与 `149-161` 两个非 DFS 块** → 四台 AP 全挤 ch36 就是没放开 149 段。
  **优化时把 5G 允许信道放开到 36–48 + 149–161，WIO 才能把 AP 拆到两个 80MHz 块。**
- **2.4G 限制到 CH.1–11**：ch12/13 是部分终端（尤其美区/旧 IoT）不支持的兼容雷区。
- 上次 WIO（2025-12-22）默认把 2.4G 规划成 **12/2/7**——这其实是有效的非重叠三信道方案，不是故障。
  **看到「多台 AP 同频道」先别急着改，确认是不是 WIO 的有意规划。**

## 6. 本户战前基线（2026-10-03，回滚参照）

| AP | IP | 2.4G | 5G | TxPower | 5G客户端/总 |
|---|---|---|---|---|---|
| 一楼 | .117 | ch12 | ch36 | 100% | 0/4 |
| 二楼 | .142 | ch2 | ch36 | 100% | 2/3 |
| 三楼 | .174 | ch7 | ch36 | 100% | 5/9 |
| 院子 | .169 | (EAP602，界面不同) | — | — | 1/1 |

全局：Country=CN｜2.4G 20MHz｜5G 80MHz｜5G优先(频段引导)=**开**｜漫游保持IP=**开**｜802.11k/v 漫游优化=**开**（扫描数据 2025-12-22）｜断开RSSI -85/-65dBm。

**问题清单**：①5G 三台全 ch36 同频 ②WIO 环境扫描 10 个月未刷新 ③AP 固件 2.380 可升级、AC 2.340 比 AP 旧 ④院子 AP 是 EAP602（异代硬件）。

## 7. 拓扑页才是首选读数入口

`admin/network/topo_map`：**点节点名（如「三楼AP」）即出详情面板**，含 MGMT IP / Working Mode /
`5G Connected: N / Total Connected: M` / 各频段 `Channel X  Tx Power Y%` / 客户端协商速率。
比逐台 Manage 点进去可靠得多。

**但设备列表的 `Manage` 索引其实可用**：Action 列是**独立表格**，按行搜 `Manage` 搜不到（行里只有用户名）→ 收集全部 `Manage` 文本节点**按序号点**：`0`=AC，`1..4` = AP 在列表中的顺序（例：三楼AP = 索引 3）。

AP 详情页客户端表字段：`Username | SSID and Band | Signal Quality | IP/MAC | Negotiation Rate | Online Duration`。
**其中 `Signal Quality`(dBm) + `Negotiation Rate` 是判「视频卡不卡」的权威数据** —— 判据表见 `references/ruijie-wio-optimization.md` 坑 2。

## 8. 浏览器驱动避坑
- **`page_info()` 返回的是 dict**，`page_info()[:800]` 会抛 `TypeError: unhashable type: 'slice'` → 写 `str(page_info())[:800]`。
- **自签名证书拦截页按文字点更稳**（id 找不到时的兜底）：先点 `/Advanced|高级/`，再点 `/Proceed to|继续前往|unsafe/`。过掉这一跳**会话也丢了**，要重走 vault 注入。

- **不要用 `goto_url` 直接跳 AC 的 URL** —— 会撞自签名证书拦截页，过掉之后**会话也没了**
  （落回登录页，要重新走一次 vault 注入）。**优先在页面内点侧边栏/顶栏菜单文字**（SPA 路由，不重载）。
- 单击菜单项**不是 `a[href]`**（是点击事件），按文字找人再点：
  `(()=>{const e=[...document.querySelectorAll('*')].filter(x=>x.children.length===0&&x.textContent.trim()==='Radio Setting')[0];if(e)e.click();return 1})()`
- 进到 AP 详情页（`/admin/alone/...`）后**侧边栏消失、`history.back()` 也回不去**；用顶栏 `Devices` 或重新导航。
- **页签内容是懒加载的**：AP 详情页的 `Monitor | Config` 单选，点了 `Config` 头几秒可能仍是空面板 ——
  多等一轮再读，别据此判定「没有这个功能」。
- 表格不是 `<tr>`（是 div 网格），**按行定位不可靠**；用拓扑页点节点名取数。

