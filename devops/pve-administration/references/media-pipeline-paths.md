# 下载 / 做种链路路径统一（qB → Tr → MP）

铁律：**同一个宿主机卷，必须在每个容器里挂成同一个路径**；转移工具的路径转换规则在挂载统一后必须变成「不转换」。任何一边单独改，都会重新制造「种子记录路径 ≠ 文件实际路径」。

## 步骤（先查后改，改前必备份）

1. **列挂载**（谁和谁不一致一眼可见）：
   ```sh
   docker inspect <c> --format '{{range .Mounts}}{{.Source}} → {{.Destination}}{{println}}{{end}}' | grep <vol>
   ```
   同时读每个容器的实际配置：qB `Session\DefaultSavePath`、`Downloads\SavePath`、`Downloads\TempPath`；Tr `download-dir` / `incomplete-dir`；MP 从挂载与 DB 配置判断。
2. **选规范路径 = 多数容器已经在用的那个**，只改少数派；改 compose 的 `volumes` 后 `docker compose up -d --force-recreate`。**绝不移动数据文件**——挂载点改了，文件位置语义自动跟着变。
3. **修配置**：
   - 容器**停着时才能改**（运行中改会被 daemon 关停时写回覆盖）→ `docker stop` → 改 → `docker start` → **启动后再验一次**，因为启动还可能再写回。
   - 停止的容器不能 `docker exec` → 用 `docker cp` 拉出来改、再 `docker cp` 推回去。
   - qB 的 `Downloads\SavePath` 是 legacy 字段但**同样会被写回**；真正生效的是 `Session\DefaultSavePath`，两者都改到同一值才叫干净。
4. **批量修正已有种子**（RPC）：`torrent-set-location` with `move: false`（文件本来就在那儿）→ `torrent-verify` → `torrent-start`。验收：`torrent-get` 的 `downloadDir` 全部等于配置值、`errorString` 全空。
5. **修转移工具的映射规则**（否则下次转移又把错路径种回来）：IYUU 在 `cn_crontab.parameter.path_convert_rule`（形如 `/A{#**#}/B` = 把 A 换成 B，挂载统一后改成 `/A{#**#}/A`）与 `cn_reseed.directory`；改完重启该容器。
6. **残留扫描只看真实配置**（`*.conf`、`settings.json`、DB 表）；日志、前端 JS、插件源码里的同名字符串是历史/默认值，不算残留，别去动。

## 「No data found / Ensure your drives are connected」分诊

- 该报错 = **种子记录的 downloadDir ≠ 文件所在**，与磁盘是否掉线无关。文件在、权限开、配置对却仍报错 → 一定是第 4 步的记录路径过期。
- **验证文件位置必须在宿主机路径上 `find`**，不能拿容器内路径去宿主机找：宿主机没有 `/Media` 或 `/downloads` 这种容器内挂载点，用它查会得出「文件全丢」的假结论。
- 顺带补建配置里引用但缺失的目录（如 `incomplete`、`complete`），否则 daemon 启动日志会持续报 `stat: No such file` 并可能影响校验流程。

## RPC / 认证要点

- Transmission 的 409 握手：POST 失败时从 `HTTPError.headers` 取 `X-Transmission-Session-Id`，**带同一个头重试**；每个新方法第一次都可能 409，封装成会自动重试的 `rpc()`。
- linuxserver 系镜像的账密写在 **compose 的 `environment`（USER/PASS）**，daemon 启动时据此**重新生成配置文件** → 改 `settings.json` 关认证永远会被写回；直接从 compose 读凭据使用，别跟它抢配置。
- 凭据只用于调用，**不打印、不落聊天**。

## 远程脚本传递（NAS / 路由器）

- NAS `user` 用户不能写 `/tmp` 或家目录 → 脚本落**数据卷下的临时目录**（如 `/volume1/docker/_tmp`），用完删。
- 路由器 BusyBox **没有 base64** → 本地 `write_file` + `scp` 传脚本再执行。
- `docker exec` 读 heredoc **必须加 `-i`**，否则脚本静默不执行（无输出、退出码 0，极易误判成功）—— 复杂内联脚本一律走 base64 管道或 base64 文件。
- `echo pw | sudo -S` 会抢走管道里脚本的 stdin → 先 `sudo -S -v <<< '<pw>'` 缓存凭据再执行。
- shell 引号/括号嵌套是主要失败源：**多行/复杂脚本远端一律传文件**；单行命令可内联，但必须整条 `shlex.quote()` 后再拼 ssh——整体 quote 过内部单引号就安全，裸 repr/f-string 拼接遇到 `'` 才会炸（repr 是 Python 引号不是 shell 引号）。

## 「校验中 → 变成下载」分诊（文件明明在，重新做种却失败）

recheck 是拿「种子记录路径 + 种子内文件名」逐字节对磁盘，任何一段对不上就判 <100% 转为下载。按序查：

1. **种子还在客户端里吗**：列表里没有 = 用户每次失败后已移除，先找回原种（见下），否则无从对比。
2. **`Download dir` 对不对**：`transmission-remote -n <u:p> -t <id> -i` 读记录路径，`settings.json` 的 `download-dir` 读默认值；按挂载把容器路径换算回宿主机路径再找文件（容器内路径在宿主机上不存在，拿它 `find` 会误判「文件全丢」）。
3. **顶层文件夹名逐字节比对**：种子 `FILES` 的第一段路径 vs 磁盘实际目录名 —— 重命名、移动、Emby/Jellyfin 刮削改名（`剧名 (2001)/Season 1/…`）会让整棵树整体找不到。
4. **缺附属文件**：磁盘只剩 `*.mp4` 而种子里还有 nfo/srt/封面 → 必然 <100%，且缺失块分散在各 piece，不是「补几 KB 就完」。加回时**只勾选磁盘上真实存在的文件**，recheck 即 100%。

**找回已移除的原种**（按命中率排序）：

```sh
# 客户端自有目录（Transmission 的 torrents/ 与 resume/ 按 hash 成对）
<config>/torrents/*.torrent        # Transmission
<config>/qBittorrent/BT_backup/*.torrent   # qB —— 多一层 qBittorrent/，找错层会得出「0 个」的假结论
# 全盘兜底（bencode 是二进制，-a 当文本才能按 UTF-8 文件名搜）
find /volume1 /volume2 -name '*.torrent' -size -10M > /tmp/tl.txt
grep -v '<客户端自有目录>' /tmp/tl.txt | xargs grep -laE '<剧名|发布组名>'
docker exec <容器> transmission-show <容器内可见路径>.torrent | sed -n '/FILES/,$p'   # 种子内文件树，与磁盘 find 结果对齐；宿主机路径容器看不见就先 docker cp
```

- 客户端与 NAS 全扫都没有 → 去**最初下载的那台设备**找（浏览器下载目录）；也都没有 → 只能回站点重下原种（私有站凭 announce URL 里的 passkey 认账号）。
- 拿不准用户动过什么，**用 mtime 还原时间线**（各集文件 mtime = 下载完成时刻；文件夹 mtime = 后期增删改名），比追问更准。

## 转移归因与标签（「这两个种子是谁转的？为啥没打标？」2026-10-10 实测）

这台 NAS 上**有两套 qB→TR 自动转移**，归因先分清是谁：

| 系统 | 调度 | 标签 | 状态 |
|---|---|---|---|
| **IYUU `iyuu:transfer`**（`cn_crontab` id=2「qb到tr」，id=1「辅种」） | 每天 12:00（`0 12 * * *`） | 取决于任务参数 `marker` | 活着；容器除非手动停不会自启失败（`unless-stopped`） |
| **MP 插件 `TorrentTransfer`「自动转移做种」** | 每天 04:00 | 硬编码 `转移做种`（`add_torrent_tags`） | **2026-10-02 11:01 起服务被移除，不再跑**；历史标签是它留下的 |

任务参数里的 `from_clients`/`to_clients` = `cn_client.id`（**1 = qB，2 = TR**）；`delete_torrent:true` = 转移后删源端——**qB 里种子消失是设计行为**，不是丢了。

**归因三步**：
1. **IYUU 的铁证表 `cn_transfer`**（主键是 `transfer_id` 不是 `id`）：每条 = 一次真实转移，含 `info_hash / directory / convert_directory / message(TR返回的 torrent-added id) / created_at`。表空 = IYUU 一次都没转过（它「运行成功」只代表调度跑了，不代表有货可转）。
2. **MP 侧**看 `/config/logs/moviepilot.log*` 里 `转移做种`/`TorrentTransfer` 的最后时间线。
3. 两边都没有 → 手动 `torrent-set-location`，如实告诉用户是手动的。

**标签机制（IYUU）**：标签在任务参数 `cn_crontab.parameter.marker`，`empty`(默认，不打标) / `tag` / `category`；TR 侧打的是**代码写死的 `IYUU自动转移`**（`IYUU`.ReseedSubtypeEnums::text(Transfer)），改不了名——想要 MP 时代的 `转移做种` 只能 `torrent-set` 手动补。改法：`UPDATE cn_crontab SET parameter='…\"marker\":\"tag\"…' WHERE crontab_id=2`（JSON 无单引号可安全单引号包）；参数在服务构造时现读 DB，**不用重启容器**。

**手动补跑（错过 12:00 的点时）**：
```sh
docker exec iyuuplus-mm php /iyuu/webman iyuu:transfer 2   # qb→tr；辅种用 iyuu:reseed 1
```
输出里「成功推送种子到下载器」才算数；随后 `cn_transfer` 应新增记录、源端 BT_backup 应清空（`delete_torrent:true`）。

**IYUU 内置 MySQL**：`docker exec iyuuplus-mm mysql -uroot iyuu`（root 无密码，库名 `iyuu`；表 `cn_crontab`/`cn_client`/`cn_transfer`）。**启动竞态是常态**：PHP cron worker 先报 `Connection refused`/`No such file` 并 `exit with status 64000`，等 mariadbd 起来后重试成功，日志出现 `Success 载入计划任务 ID 1/ID 2` 即健康——看到前半段报错别当死了，看到这行才算活。

**归因辅助**：`cn_crontab.last_running_time`（unix 秒）对照任务的 rule，可直接算出「哪几天的点没跑到」；容器 `docker ps -a` 的 `Exited (255)` + `FinishedAt` 对上断档区间即可定案。

**大种子校验的正常体感**：TR `status=2 checking` + `percentDone=1.0` 是正常的（校验完才落定）；264.5G 在这台机约 **110 MB/s 读速 ≈ 41 分钟**。真在校验用 `/proc/diskstats` 两次采样算读增量证明（本例 md2/sdb 110MB/s）；「校验中→变成下载」才是出事（见上节分诊）。

## 收到用户的 .torrent、数据已在盘 → 挂种重做种

顺序写死：**解析 → 算路径 → paused 添加 → 显式 verify → start**，一步都别跳。

1. **先解析种子核对**：bencode 解出 `infohash`/`private`/文件树；**文件树第一段目录名必须与磁盘现有目录逐字节一致**（同「校验中→变成下载」分诊第 3 条）。私有站的 announce URL 自带账号 passkey，直接可用。
2. **路径算对（最大的坑）**：多文件种子落盘在 `<download-dir>/<info.name>/`，所以 `download-dir` 指现有文件夹的**上一级**；按 `docker inspect` 的 mounts 把宿主机路径换算成容器路径，拿 TR `settings.json` 的现值当参照对一遍——**差一层就是整包重下**。
3. **paused 添加 + 显式 verify**：`torrent-add` 带 `metainfo`（base64）+ `paused:true` + `download-dir`，响应用 `torrent-added`（`torrent-duplicate` = 已存在，别重复加）；409 握手见「RPC / 认证要点」；然后 `torrent-verify` → 轮询 `status`。
4. **状态判读**：`1/2`=checking 正常（时长体感见上节）；`0` + `percentDone=1` → `torrent-start` → `6`=seeding 收工；**`3/4` = 路径没对上正在重下——立刻停手处理，这不是「再等等」的事**。
5. **别省 paused 直接 start**：先暂停的意义是让路径错误暴露在 verify 阶段，而不是在 start 后变成几百 GB 的下载。

## 大校验的看护（会自己回来报信）

- 长 recheck（几十分钟）别占着会话等：外层 terminal `background=true` 跑一个轮询脚本（读 `status`/`percentDone`，`1/2` 继续睡、`0`+`pct=1` 自动 `torrent-start`、`3/4` 打 ALARM 立刻退出），再建一次性 `cronjob` 到预计完成时间做独立复核——双保险，用户到点能收到确认。
