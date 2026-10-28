# OpenClash 版本升级配方（插件 ipk + Mihomo 内核）

适用：插件/内核落后、升级后服务起不来、需要回滚。
先看 SKILL.md 的「OpenClash 服务不起来 / 版本升级」三分表定位现象，再照下面执行。

## 1. 备份三件套（缺一个就可能回不去）

```bash
TS=$(date +%Y%m%d-%H%M%S); mkdir -p /root/oc-backup
tar czf /root/oc-backup/openclash-config-$TS.tar.gz /etc/openclash          # 全量配置
cp /etc/config/openclash /root/oc-backup/config.openclash.$TS               # UCI
cp /etc/openclash/core/clash_meta \
   /root/oc-backup/clash_meta.$(cat /etc/openclash/core/clash_meta_version) # 旧内核
```

## 2. 看当前版本 + 找最新版

```bash
# 当前
grep '^Version:' /usr/lib/opkg/info/luci-app-openclash.control   # 插件
cat /etc/openclash/core/clash_meta_version                       # 内核
uci get openclash.config.core_version                            # 例: linux-amd64-v1

# 最新（GitHub 必须走代理，路由器自己下不动）
curl -s -x http://192.0.2.10:7890 'https://api.github.com/repos/vernesong/OpenClash/releases?per_page=3' \
  | grep -E 'tag_name|browser_download_url.*ipk'
curl -s -x http://192.0.2.10:7890 'https://api.github.com/repos/MetaCubeX/mihomo/releases?per_page=8' \
  | grep -E 'tag_name|prerelease'      # 跳过 prerelease（Alpha）
```

内核资产名必须匹配 `core_version`：`linux-amd64-v1` → `mihomo-linux-amd64-v1-vX.Y.Z.gz`（不是 `mihomo-linux-amd64-vX.Y.Z.gz`）。

## 3. 本机下载 → scp 上路由器

在有代理的机器上下载两个文件，`scp -P 2222` 传到路由器 `/tmp/`（BusyBox **无 `base64`**，别想用管道把脚本或文件灌进去）。

```bash
gzip -t /tmp/mihomo-new.gz && echo OK          # 走代理偶尔给截断文件
```

## 4. 停服务 → 先测新内核能跑，再覆盖

```bash
/etc/init.d/openclash stop
gunzip -c /tmp/mihomo-new.gz > /etc/openclash/core/clash_meta.new
chmod 755 /etc/openclash/core/clash_meta.new
/etc/openclash/core/clash_meta.new -v          # ← 测不过就放弃，绝不动旧内核
# 通过后再交换，并更新版本标记文件
mv /etc/openclash/core/clash_meta.new /etc/openclash/core/clash_meta
echo 'vX.Y.Z' > /etc/openclash/core/clash_meta_version
```

**先测再覆盖**是这套流程里唯一不能省的一步：内核起不来时，你还指望旧内核能救场。

## 5. 装插件 ipk + 查开关（跳过 = 「升完打不开」）

```bash
opkg install /tmp/luci-app-openclash_*.ipk
grep '^Version:' /usr/lib/opkg/info/luci-app-openclash.control   # 确认新版本

# ipk 安装会把 enable 重置成 0，必须设回来
uci set openclash.config.enable='1'; uci commit openclash
/etc/init.d/openclash enable      # 自启：没有这条，下次重启又 inactive
/etc/init.d/openclash start
```

## 6. 验收（只认端口实测，不认 status 字样）

```bash
/etc/init.d/openclash status; ps | grep -c '[c]lash'
curl -s -o /dev/null -w '%{http_code}\n' -m 15 \
  -x http://127.0.0.1:7890 https://www.google.com/generate_204    # 204 = 通
curl -s -o /dev/null -w '%{http_code}\n' -m 15 \
  -x http://127.0.0.1:7890 https://www.youtube.com
/etc/init.d/openclash enabled && echo autostart-ok
```

代理返回 407 → 认证还开着（`openclash.@authentication[0].enabled=1`），按需关掉或让客户端带账密。

## 7. 回滚

```bash
/etc/init.d/openclash stop
tar xzf /root/oc-backup/openclash-config-*.tar.gz -C /            # 配置 + 旧内核(在 core/ 里)
cp /root/oc-backup/config.openclash.* /etc/config/openclash; uci commit openclash
opkg install /root/oc-backup/旧版本.ipk                            # 需自行留档旧 ipk
/etc/init.d/openclash enable; /etc/init.d/openclash start
```
