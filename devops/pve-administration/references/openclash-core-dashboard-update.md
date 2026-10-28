# OpenClash 内核 / 仪表盘更新（iStoreOS x86）

## ⚠️⚠️ 最大的坑：GOAMD64 微架构变体选错 = 内核起不来 = 全屋断网

mihomo 的 release 资产名里有微架构分级，**默认那个（无后缀）是 v3，需要 AVX2**：
```
mihomo-linux-amd64-alpha-9f053c4.gz        ← GOAMD64 v3，需 AVX2 ✗
mihomo-linux-amd64-v1-alpha-9f053c4.gz     ← GOAMD64 v1 ✓ 最大兼容
mihomo-linux-amd64-v2-alpha-...gz          ← SSE4.2/POPCNT/CX16
mihomo-linux-amd64-compatible-...gz        ← 更老 CPU
```
**选错的表现（必须记住）：**
```
This program can only be run on AMD64 processors with v3 microarchitecture support.
```

### 家庭路由器 CPU 对照
| CPU | 指令集 | 可选 |
|---|---|---|
| Intel J4125 / N5105 (Goldmont) | sse4_2 popcnt cx16 movbe，**无 AVX** | **v1**（OpenClash 默认配 `core_version='linux-amd64-v1'`）|
| 有 AVX2 的机器（i3/i5 8代+） | 带 avx2 | v2 / v3 |

**查指令集：** `grep -oE "avx2|sse4_2|popcnt" /proc/cpuinfo | sort -u`
**以 OpenClash 配置为准：** `uci show openclash | grep core_version` → 选同名变体。

## 铁律：先预检，再替换
**绝不能直接 mv 覆盖。**正确顺序：
```sh
# 1) 解压到 /tmp（不动现场）
gzip -dc /tmp/新内核.gz > /tmp/clash_alpha && chmod 4755 /tmp/clash_alpha
# 2) 预检 A —— 二进制能不能跑（这条拦住过事故）
/tmp/clash_alpha -v      # 报微架构错 → 中止，重新下 v1
# 3) 预检 B —— 配置能不能过
/tmp/clash_alpha -t -d /etc/openclash -f /etc/openclash/9.1.yaml
grep -v "^external-ui" /etc/openclash/9.1.yaml > /tmp/cfgtest.yaml   # 排除误报
/tmp/clash_alpha -t -d /etc/openclash -f /tmp/cfgtest.yaml           # 必须 "test is successful"
# 4) 都过了才替换
cp -a /etc/openclash/core/clash_meta $BD/clash_meta.bak
mv -f /tmp/clash_alpha /etc/openclash/core/clash_meta && chmod 4755 /etc/openclash/core/clash_meta
# 5) 重启（全屋 15~40s 断网，必须提前告知用户）+ 验证
/etc/init.d/openclash restart
curl -s -H "Authorization: Bearer <secret>" http://127.0.0.1:9090/version
```

## external-ui 报错是“假致命”
`external-ui: "/usr/share/openclash/ui"` 会让 `-t` 报 `path is not subpath of home directory or SAFE_PATHS`，**但运行时只是警告，内核照常启动**（日志会出现 `UI already exists, skip downloading`）。验证时把它 grep 掉再测，否则会误判配置坏。

## 版本记录文件 /etc/openclash/core/clash_meta_version
单行文本，**`-v` 输出有多行，用 `awk '{print $3}'` 会把第二行也写进去**：
```
# 错误结果（踩过）: alpha-9f053c4\nwith_gvisor
# 正确做法：
printf 'alpha-9f053c4\n' > /etc/openclash/core/clash_meta_version
```

## 为什么不用 openclash_core.sh 自动更新
`/usr/share/openclash/openclash_core.sh` 要求输入 **`.tar.gz`（内含名为 `clash` 的文件）**，而 GitHub 上游发布的是**裸 `.gz`** → 直接喂会被 `tar` 拒绝。
它支持传 URL（`$2` 匹配 `^https?://` 即用），但要自己先打包。**手动替换 + 预检反而更可控。**

## 仪表盘（zashboard）更新 —— 不需要重启
```sh
# 下载 GitHub release 的 dist.zip（约 9.5MB）→ 本地解压出 dist/
# 备份: tar czf $BD/zashboard-old.tar.gz -C /usr/share/openclash/ui zashboard
tar xzf zash-new.tar.gz -C /tmp/zash-x
rm -rf /usr/share/openclash/ui/zashboard && mv /tmp/zash-x/dist /usr/share/openclash/ui/zashboard
chmod -R 755 /usr/share/openclash/ui/zashboard
```
**静态目录由内核直接服务，改完即生效、不重启 ✓**

**验证：** `curl -H "Authorization: Bearer <secret>" http://127.0.0.1:9090/ui/zashboard/index.html` 返回的字节数要等于新构建 `dist/index.html` 的大小。

**⚠️ 必须提醒用户：PWA 有 Service Worker 缓存，不硬刷新会一直看到旧版** → 桌面 Ctrl+Shift+R，移动端清除站点数据。

## 关键路径速查
| 项 | 路径 |
|---|---|
| 内核二进制 | `/etc/openclash/core/clash_meta`（`/etc/openclash/clash` 是软链）|
| 版本记录 | `/etc/openclash/core/clash_meta_version` |
| 仪表盘目录 | `/usr/share/openclash/ui/{zashboard,metacubexd}/` |
| 切换启用哪个仪表盘 | `9.1.yaml` 的 `external-ui-name` |
| 内核启动命令 | `/etc/openclash/clash -d /etc/openclash -f /etc/openclash/9.1.yaml` |
| 内核/RESTful API 密钥 | `uci show openclash | grep dashboard_password` |
