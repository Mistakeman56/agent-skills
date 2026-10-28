---
name: ruijie-ac-api
description: the user asks about 锐捷AC漫游/信道/AP状态时用，读 SSH 关闭的锐捷设备配置。
---

# 锐捷 EG/Reyee 网关 eWeb API

设备：**锐捷 EG210G-P** 网关兼 AC，`192.0.2.10`，web 账 `admin`（密码见记忆里「锐捷AC」条目）。SSH/Telnet 默认关，**唯一入口是 eWeb 的 JSON API**。AP×4：一楼/二楼/三楼 EAP262(E)、院子 EAP602，SSID `user`。

## 1. 登录拿 sid

```bash
# 密码加密：GibberishAES（OpenSSL 兼容），设备给了固定密钥
# aes.js 在 https://192.0.2.10/luci-static/eweb-egw/static/aes.js（gzip，要解压）
# Node 里（UMD，module.exports 直接可用）：
const GA=require('/tmp/ruijie/aes.plain.js');
const cipher=GA.enc(pw,'469fc1c074cf5b593c1dc0b7cc1de0c5').replace(/\s+/g,'');

curl -sk -X POST -H 'Content-Type: application/json' \
  -d '{"method":"login","params":{"username":"admin","time":"<unix>","encry":true,"pwd":"'$cipher'"}}' \
  https://192.0.2.10/cgi-bin/luci/api/auth
# → {"code":0,"data":{"token":"...","sid":"<32hex>"}}  sid 存文件后续用
```

## 2. 调用格式（关键坑）

```bash
POST https://192.0.2.10/cgi-bin/luci/api/<module>?auth=<sid>
Cookie: ZARC0KT007974=<sid>   # 非必需
Body:   {"method":"...","params":{"module":"...","data":{...}}}
```

- **必须带 `?auth=<sid>`**：只带 Cookie 会 `403 Forbidden`。
- **不需要** 前端那两个 `Content-Accept`/`Contents-Accept` md5 头（试过会 404）。
- `<module>` 只有这些：`advanced auth cmd common diagnose file network openvpn overview quickset switch system wireless`，**99% 的调用走 `cmd`**。
- `cmd` 的 `method` = `<前缀>.get/set`，前缀映射 `_MAP = {ac_config:acConfig, dev_config:devConfig, dev_sta:devSta, dev_cap:devCap}`，来自 apiConfig 里的 shell 串，例如：
  - `wireless → ac_config get -m wireless` ⇒ `acConfig.get {module:'wireless'}`（**AC 侧 SSID 配置在这里**）
  - `wioStatus → dev_config get -m wio` ⇒ `devConfig.get {module:'wio'}`
  - `wioRes → dev_sta get -m wio $data` ⇒ `devSta.get {module:'wio', data:{mode:'aplist'|'wioV2status'|'is_need_wio'}}`
  - `staList → dev_sta get -m sta_list` ⇒ `devSta.get {module:'staList'}`（**在线客户端：mac/ip/sn/band/channel/rssi/rxrate/hostName**）
  - `neighbor → dev_sta get -m neighbor`（**AP 列表：ip/devMac/devSN/software/forwardMode/tipcInst**）
  - `kvNavAc → ac_config get -m kvNavAc`（**802.11k/v 开关**：`roamNavEnable`/`kvAiEnable`/`amrEnable`/`snfEnable`）
  - `wiov2Global → ac_config get -m wioV2`、`radioLb → ac_config get -m radioLb`（AP 负载均衡）、`wioTime → dev_config get -m wio_time`
- 完整 name→shell 表（481 条）可从前端 bundle 里正则抽：`r\(\)\(n,"([A-Za-z0-9_.]+)",(?:"([^"]+)"|\{shell:\s*"([^"]+)")`，bundle 在 `/luci-static/eweb-egw/static/js/app*.js` 和 `wifi*.js`（要 `--compressed`）。

## 3. 已知坑

- **method 前缀错了不报错**：返回 `{code:0, data:{code:0,data:""}}`（看着像空数据，其实是路由没命中）；`devConfig.get` 用错 module 会回 `{rcode:'03510001', rmsg:'UF:get config fail...'}`。
- **`devSta.get {module:'roam'}` 会挂死**（>60s 无响应），别放进批量轮询。
- `ac_config get -m apList` 回 UF 失败 —— AP 状态别从这儿拿，用 `neighbor` + `staList`。
- `devSta.get {module:'radioInfo'}` 只回 `radio0/radio1 {channel:NULL}`（网关本机没开 Wi-Fi），**别当成 AP 的信道**；AP 信道用 `staList` 里的 `channel` 或 WIO record field `cc`。
- 登录失败会锁（3 次=1 分钟），**别拿密码试错**；先拿 `overview.getDeviceInfo` 之类无害方法验证会话。
- 想知道前端怎么调，别猜，直接 grep bundle：`$apiArr("name")` / `{module:"x",data:{...}}` 调用点就写着完整参数。

## 4. 漫游巡检要读的字段

| 目标 | 调用 | 字段 |
|---|---|---|
| SSID 漫游能力 | `acConfig.get {module:'wireless'}` | `ssidList[0]`：`ft`(11r)、`okc`、`bandSelectEnable`(5G优先)、`xpress`、`relatedRadio`(双频合一)、`encryptionMode`、`password` |
| 802.11k/v | `acConfig.get {module:'kvNavAc'}` | `global.roamNavEnable`(11v)、`kvAiEnable`、`amrEnable`、`snfEnable` |
| 无线优化 | `devConfig.get {module:'wio'}` + `devSta.get {module:'wio',data:{mode:'wioV2status'}}` | `start`、`optiStatus`、`wioV2StartTime/EndTime`、`optiDegree` |
| 优化排程 | `devConfig.get {module:'wio_time'}` | `enable`、`time`、`week` |
| 射频参数 | `acConfig.get {module:'wireless'}` | `radioList`：`bandWidth`(2.4G=20/5G=80)、`kicksta_rssilow`(弱信号踢除，0=关) |
| 负载均衡 | `acConfig.get {module:'radioLb'}` | `enable`、`max_diff`、`start_num` |
| 还能不能优化 | `devSta.get {module:'wio',data:{mode:'is_need_wio'}}` | `reason: "WIO can be carried out."` |
| 各AP优化前后 | `devSta.get {module:'wio',data:{mode:'aplist'}}` | `ap_list[].rlst[]`：`co/cc`(原/现信道)、`bo/bc`(带宽)、`po/pc`(功率)、`channelList[]`(逐信道 noise/util/外部干扰AP数/score) |
| 客户端质量 | `devSta.get {module:'staList'}` | 按 `sn` 分组，`rssi`、`band`、`channel`、`rxrate`、`onlineTime` |

**注意**：`devConfig.get {module:'wireless'}`（dev_config 路）只回**网关本机**那份（SSID 可能是 `@Ruijie-mD0CC`），**AC 全局 SSID 要走 `acConfig.get {module:'wireless'}`**（才是 `user` 那份）。

## 5. 只读原则

写操作走 `ac_config set -m wireless $data` / `dev_config set -m wio $data`，**会让射频重启、全部客户端掉线几秒到十几秒**，未经 the user explicitly点头不要执行。