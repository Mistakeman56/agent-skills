# OpenClash 维护：开机自启、代理认证、插件与内核升级

触发：「OpenClash 明明开着但代理不好用」「它版本/内核是不是太低了，要不要更新」，或需要动 OpenClash 插件/内核版本时。

## 第一步：分清三种「开了但不好用」（可叠加，逐个排除）

用户说「开了」通常只看到 LuCI 里的开关，**不代表服务在跑**。

```sh
/etc/init.d/openclash status                 # running / inactive
/etc/init.d/openclash enabled && echo 自启已开 || echo 自启未开
ps | grep -E '[c]lash' | head -3
uci show openclash | grep -iE 'config\.(enable|core_version)|authentication\[' | sed -E 's/(password|secret)=.*/\1=***/'
```

★ 用 `grep '[c]lash'`（括号技巧）而不是 `grep clash | grep -v grep`：BusyBox 上更短、不会把 grep 自己算进去，也不会因引号嵌套拼坏。

### 因 A：`enable=1` 但服务 `inactive` → 开机自启没注册

`openclash.config.enable='1'` 只是配置层的开关，与 init 自启是两件事。设备只要重启过一次（含 PVE 重启/断电），服务就不会自己起来，之后一直 inactive —— 表现正是「明明开着，代理却不好用」。

```sh
/etc/init.d/openclash enable
/etc/init.d/openclash enabled && echo OK
/etc/init.d/openclash start
```

### 因 B：代理认证 → 应用侧 HTTP 407

```sh
curl -s -o /dev/null -w '%{http_code}\n' -m 10 -x http://127.0.0.1:7890 http://www.baidu.com   # 407 = 认证拦的
curl -sv -m 8 -x http://127.0.0.1:7890 http://www.baidu.com 2>&1 | grep -E '^< HTTP|^< Proxy'
#   < HTTP/1.1 407 Proxy Authentication Required
#   < Proxy-Authenticate: Basic
```

认证开关在 **UCI**，不一定会写进 yaml —— **两边都要查**：

```sh
uci show openclash | grep -iE 'authentication'                   # enabled / username / password
for f in /etc/openclash/config/*.yaml; do grep -H -i '^authentication:' "$f"; done   # 多数为空
```

- **关掉**（内网自用推荐，开箱即用）：
  ```sh
  uci set openclash.@authentication[0].enabled='0'; uci commit openclash; /etc/init.d/openclash restart
  ```
- **保留**：则每个使用它的应用都必须带 Basic 凭据（`http://user:pass@ip:7890`），否则一律 407。多数「应用连不上代理」的真实解释就是这个，而不是代理坏了。
- external-controller 若设了 `secret`，API 会回 `{"message":"Unauthorized"}` —— 别误当成服务挂了。

★ **回显 UCI 时给凭据打码**：`| sed -E 's/(password|secret)=.*/\1=***/'`。这些值不该进对话记录。

### 因 C：版本落后（见下节升级）

## 升级（插件 + 内核）

### 0. 备份（必须，先做）

```sh
mkdir -p /root/oc-backup
tar czf /root/oc-backup/openclash-config-$(date +%F-%H%M).tar.gz /etc/openclash
cp /etc/openclash/core/clash_meta "/root/oc-backup/clash_meta.$(cat /etc/openclash/core/clash_meta_version)"
cp /etc/config/openclash /root/oc-backup/config.openclash.before-update
```

### 1. 取版本与资产名（在 Hermes 主机上走 7890 代理下载；路由器直连 GitHub 慢/不通）

```sh
P=http://192.0.2.10:7890
# 插件 tag + ipk 名
curl -s -x $P 'https://api.github.com/repos/vernesong/OpenClash/releases?per_page=3' \
  | grep -E '"tag_name"|"prerelease"|luci-app-openclash.*\.ipk'
# 内核 tag：取 prerelease=false 里最高的；Prerelease-Alpha 是预发布，不要用
curl -s -x $P 'https://api.github.com/repos/MetaCubeX/mihomo/releases?per_page=8' \
  | grep -E '"tag_name"|"prerelease"'
# 内核资产名（必须与 core_version 对应）
curl -s -x $P 'https://api.github.com/repos/MetaCubeX/mihomo/releases/tags/<tag>' \
  | grep -oE '"name": "mihomo-linux-amd64[^"]*"'
```

★ **内核资产名必须匹配 `openclash.config.core_version`**：该值为 `linux-amd64-v1` 时对应 `mihomo-linux-amd64-v1-<ver>.gz`。同页还有 `-v2-` / `-v3-` / `-compatible-` / `-go120-` / `-go123-` 变体，下错会被判为版本不符。下载后**先在本机验证再往设备上放**：

```sh
gzip -t x.gz && gunzip -c x.gz > /tmp/x && chmod +x /tmp/x && /tmp/x -v
```

传输用本机 `scp -P <port>` 直传路由器 `/tmp`（几十 MB 无压力）。★ 路由器是 BusyBox，**没有 `base64`**，一律「本地 write_file/scp」，不要用 base64 管道。

### 2. 换内核

```sh
/etc/init.d/openclash stop
gunzip -c /tmp/mihomo-new.gz > /etc/openclash/core/clash_meta.new
chmod 755 /etc/openclash/core/clash_meta.new
/etc/openclash/core/clash_meta.new -v          # 先验证可执行
mv /etc/openclash/core/clash_meta.new /etc/openclash/core/clash_meta
echo v<新版本> > /etc/openclash/core/clash_meta_version
```

`/etc/openclash/clash` 是指向 `core/clash_meta` 的软链，所以只换 `clash_meta`；`clash_meta_version` 要一起写，OpenClash 靠它显示/校验版本。

### 3. 装插件

```sh
opkg install /tmp/openclash-new.ipk
grep '^Version:' /usr/lib/opkg/info/luci-app-openclash.control
```

`remove_obsolesced_files: unlinking ... failed: No such file or directory` 一串是**正常噪音**；以最后出现 `Configuring luci-app-openclash.` 且版本号变了为准。

### 4. ★ 升级后必做：`enable` 被重置成 0

新版升级（实测 0.47.055 → 0.47.156）会把 `openclash.config.enable` **重置为 `0`**，此后 CLI 启动被直接拒绝：

```
[Warning] OpenClash Now Disabled, Need Start From Luci Page, Exit...
```

```sh
uci set openclash.config.enable='1'; uci commit openclash; /etc/init.d/openclash start
```

**这不是故障、不是配置坏**——别在这个提示后面继续翻配置文件。用 `clash -f <在用配置> -t` 排除配置问题（打印 `configuration file ... test is successful` = 配置没问题，方向就在 enable）。
同时**逐项核对** `enable_redirect_dns` / `enable_udp_proxy` / `enable_rule_proxy` 有没有被一起重置，别默认它们保留原值。

### 5. 验收（全绿才算完）

```sh
/etc/init.d/openclash status            # running
/etc/init.d/openclash enabled           # 自启在
/etc/openclash/clash -v                 # 新版本号
netstat -lntp | grep -E '7890|9090'     # 端口在听
curl -s -o /dev/null -w '%{http_code}\n' -x http://127.0.0.1:7890 https://www.google.com/generate_204   # 204
curl -s -o /dev/null -w '%{http_code}\n' -x http://127.0.0.1:7890 http://www.baidu.com                 # 200
```

### 6. 回滚

```sh
cp /root/oc-backup/clash_meta.<旧版本> /etc/openclash/core/clash_meta
echo <旧版本> > /etc/openclash/core/clash_meta_version
tar xzf /root/oc-backup/openclash-config-<ts>.tar.gz -C /
/etc/init.d/openclash restart
```

## 坑

- **`date: invalid date '%H:%M:%S'`、`OpenClash Already Start!` / `Already Stop!`**：BusyBox 与启动脚本的噪音，与故障无关，别去追。
- **升级重置的是 UCI 开关，`/etc/openclash/config/*.yaml` 与其余设置基本保留** —— 但整目录仍要备份，回滚才有底。
- **当前跑的是哪个配置**：`uci get openclash.config.config_path`（例 `/etc/openclash/config/9.1.yaml`）；`/etc/openclash/*.yaml`（根目录）是 OpenClash 生成的运行时副本，端口/规则可能与 config/ 下的不同 → 见 `openclash-config-mismatch-diagnosis.md`。
- **407 是双面证据**：它既证明「端口活着」（见 `openclash-config-mismatch-diagnosis.md`），也可能是「应用连不上」的原因（本文因 B）。判断看**谁在报错**：手动 curl 得到 407 而服务正常 → 只是这次没带凭据。
- **三个因可同时存在**：只修一个仍不通就继续查下一个，别在第一处停下。
- **动 OpenClash 之前先看用户是否在用代理**；`uci commit` + 重启对应服务，**绝不** `fw3 flush` / 整机 reboot。
