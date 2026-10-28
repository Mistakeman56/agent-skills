# OpenClash 体检与维护（iStoreOS 路由器）

主参考是 devops/openclash-user-guide（官方指南路由表 + 调试日志纪律）；本文件只放实操体检流程与维护坑。

## 体检流程（按序执行）

1. 生成官方调试日志（约1800行/30章节）：
   ```sh
   ssh -p2222 root@ROUTER '/usr/share/openclash/openclash_debug.sh >/dev/null 2>&1'
   scp -P2222 root@ROUTER:/tmp/openclash_debug.log /tmp/
   ```
2. YAML 校验（🟡安全，不重启核心）：
   ```sh
   CP=$(uci -q get openclash.@openclash[0].config_path)
   /etc/openclash/clash -t -d /etc/openclash -f "$CP"
   ```
   必须输出 `configuration file ... test is successful`。
3. 单实例检查：`ps | grep -c '[o]penclash/clash -d'` 应为 1，看门狗 `openclash_watch` 在跑。
4. 依赖与冲突：依赖项 + `lsmod` 内核模块齐全，无 passwall/ssr-plus 等同类插件并存。
5. 防火墙链：`nft list ruleset | grep openclash` 应见 DNS劫持 / REDIRECT / 中国IP绕行链。
6. 流量双验证：百度直连 200（路由器本机 curl）+ 谷歌走代理 200（**从内网客户端**，见坑3）。
7. 日志级别一致性（见坑1）。

## 坑1：调试工具会把运行日志留在 debug

`openclash_debug.sh` 采集时把运行核心切到 debug，之后**不一定切回**，配置文件仍是 info → 日志暴涨。

- 诊断：`grep -c 'level=debug' /tmp/openclash.log` 远大于 0，而配置写 info。
- 修复（热切，不断流不重启）：
  ```sh
  curl -s -X PUT -H "Authorization: Bearer <secret>" -H "Content-Type: application/json" \
    -d '{"log-level":"info"}' http://127.0.0.1:9090/configs   # HTTP 204
  ````
  改完 sleep 数秒后 `tail` 日志，确认新行只有 info/warning。

## 坑2：GEO/数据文件可能存着 HTTP 错误页

下载失败时会把 404 错误页当数据存盘（geoip.metadb 曾只有 9 字节、内容 "Not Found"）。

- 下载后必须看体积：正常 geoip.metadb ≈ 8MB；可疑小文件先 `head -c 100` 确认不是 HTML/Not Found。
- 源 URL 在 `/usr/share/openclash/res/default.yaml`（`mmdb:` 字段）；坏文件先 `cp` 备份再 `curl -sL <url> -o` 重拉，替换后**必须重跑 `clash -t`**。
- 缺 `ASN.mmdb` / `Model.bin` 不是问题：配置没用 ASN 规则、`smart_enable=0` 时本就不需要。

## 坑3：路由器本机 curl 走不通代理 ≠ 代理坏了

路由器「本机代理」通常停用，路由器上直接 `curl https://www.google.com` 返回 000 是预期行为。验证代理要换**内网客户端视角**：

```sh
curl -sI -m 8 --proxy http://192.0.2.10:7890 https://www.google.com
```

## 坑4：核心只能用 init.d 管理

重启/停止只用 `/etc/init.d/openclash {start|restart|stop}`；**绝不手动 nohup 启 mihomo**——看门狗会检测不到而再拉一个，双进程抢端口导致断网。

## oaf/appfilter 已永久退役

`enable=0` + 自启关 + `rmmod oaf`，配置备份 `/root/appfilter.bak.<时间戳>`。再遇「凌晨 App 被 RST」类问题不怀疑 oaf，也不要重新 arm；确需恢复时从备份 `uci import`。
