# PT 转移做种 — qBittorrent ⇄ Transmission 多下载器保种

同一份数据在两个下载器之间交接（下载用 qB、保种用 Tr，或反过来）时，**真正会失败的不是路径，是站点**。

## 核心机制：站点 tracker 认「位置」= passkey + IP，不认你的目录

announce 返回 `You cannot seed the same torrent in the same location from more than 1 client.` 时：

- **这是站点的业务拒绝，不是客户端故障**。`lastAnnounceSucceeded=True`（HTTP 层成功）、`seederCount` 能读到（站点数据可达），但目标客户端拿不到做种资格，`error=1` 并在 start 后几秒自动回到 `STOPPED`。
- **触发条件**：源客户端刚刚 announce 过同一 info_hash，站点记录还没超时（announce interval × 1.5，一般 30–60 分钟），此时目标客户端立刻 announce → 站点看到同 passkey 两个 client。
- **源客户端删任务不等于站点知道**：删除不发 announce，站点只能等超时。
- **判据**：`lastAnnounceTime` 是几分钟前 = 还在窗口内；`torrent-start` 后 20 秒仍 `STOPPED` + `error=1` = 拒绝持续。
- **解法只有一条时间轴**：撤源 → 等满 ≥1 小时 → 再转移并启动目标。反复 `torrent-start` / `reannounce` 不会提前解锁，只会刷错误日志。

**因此转移必须是「撤源 → 固定延迟 → 转移」的两段式，而单个转移插件只有一次 cron、没有延迟能力** —— 用两个 cron 错开实现，而不是指望某个插件的 delay 参数（MP 与 IYUU 的转移插件都没有）。

## 推荐时序（三件套，全在 NAS 内自动跑）

```
T+0     QbCommand pause_cron        撤掉源下载器全部任务（停止 announce）
T+60m   转移插件 cron               转移 + 删源 + 启动目标（此刻站点已超时）
T+90m   QbCommand resume_cron       恢复源下载器剩余任务（下载中的续传）
```

- **转移任务只能启用一个引擎**：MP `TorrentTransfer` 与 IYUU `iyuu:transfer` 同时 enabled 会在两个时点各跑一次，第二次要么撞站点、要么重复删源。选定一个后把另一个 `enabled=false` 并 reload。
- 撤源时源下载器若为空属正常（无害）；`resume_cron` 放在转移之后 30 分钟，给批量转移留够时间，也给转移失败留出自愈余地（源没被删则被恢复做种）。

## 路径映射：首选统一挂载点（消灭翻译），次选前缀替换

本机实例（修前）：qB 容器 `/Media`、Tr 容器 `/downloads`，宿主机都是 `/volume2/downloads0` —— 同一个卷在不同容器里叫不同名字，整条链路就得永久维护一条翻译规则。

### 首选：把挂载点统一，翻译规则改成恒等

两个客户端都是自己起的容器时，**不要长期养着一条路径翻译规则**。改一个不一致的容器，把三份状态（客户端配置 / 种子记录 / 转移引擎规则）收敛成一份：

1. **先量再改**：`docker inspect <c> --format '{{range .Mounts}}{{.Source}} → {{.Destination}}{{println}}{{end}}'` 逐个查，找出少数派（qB、MP 都是 `/Media` → 只改 Tr 一个）。
2. **改 compose 挂载** `…/downloads0:/downloads` → `…/downloads0:/Media`，同时改客户端 `download-dir` / `incomplete-dir`，然后 `docker compose up -d --force-recreate`。**挂载改动必须 recreate，`docker restart` 不会重读 compose**。
3. **已有种子的记录要跟着改**（见下方 `torrent-set-location move:false`）—— 只改配置不改种子，等于把错误从客户端搬到种子上。
4. **转移引擎的翻译规则改成恒等**：IYUU `path_convert_rule` 由 `/Media{#**#}/downloads` 改成 `/Media{#**#}/Media`，并 `UPDATE cn_reseed SET directory='/Media'`。**只改客户端不改转移引擎，下一次转移就把旧前缀写回种子**——这是「修了又复发」的典型来源。
5. **验收扫残留到 0**：两个客户端的 conf + IYUU 相关表的 `LIKE '%/旧前缀%'`。**只扫真实配置**（conf / DB）；日志与前端打包 JS 里的字面量是历史噪音，算进去永远清不完。

理由：翻译规则是一条会漂移的活动部件（客户端改目录、引擎改规则、种子记录是第三份独立状态），统一挂载点让三者恒等；**靠定时自检去比对三份状态属于补丁，不是修复**。

### 次选：前缀替换（仅当挂载点改不动时）

- **物理同一目录 → 转移只挪 `.torrent`，不搬数据**，`percentDone` 保持 1.0，校验秒过。
- **但目标客户端必须拿到它自己命名空间的路径**，否则 `No such file or directory` / 校验归零重新下载。所以转移前必须做前缀替换：`/Media` → `/downloads`。
- 先用 `docker inspect` 证明两个客户端的 mount 源相同，再决定映射规则；**不要假设名字相近的路径指向同一目录**。

## 整批种子报 `No data found! … use "Set Location" / "Verify Local Data"`

**先怀疑「种子记录的目录 ≠ 当前配置的目录」，不要怀疑文件丢了。** 一步定性：`torrent-get` 取每个种子的 `downloadDir`，与 `session-get` 的 `download-dir` 对比；再拿 `files[0].name` 拼两条路径分别 `os.path.exists`。典型现场：所有种子 `downloadDir=/downloads`、session 已是 `/downloads/未整理` → 客户端去旧前缀找，文件一个没少。

排除三个假象（顺序固定，先证存在再谈修复）：
1. 存储：`df -h /volume2` + `ls /volume2/downloads0/未整理 | wc -l`（数字对得上就是好的）；
2. 容器挂载：`docker exec <容器> ls /downloads/未整理 | wc -l`，应与宿主一致；
3. **绝不在宿主机用 Python `os.path.exists('/downloads/…')` 判存在** —— 宿主机没挂这个路径，必然全 False，会得出「文件全没了」的假结论；容器内路径只能在容器里验（上一步的 `docker exec`）。

修复三连（**只改记录，不碰数据**）：
```py
rpc("torrent-set-location", {"ids": all_ids, "location": "/downloads/未整理", "move": False})
rpc("torrent-verify", {"ids": all_ids})   # UI 提示的 Verify Local Data
rpc("torrent-start",  {"ids": all_ids})
```
`move: false` 是关键 —— 数据本来就在这儿，`true` 会触发无谓移动；几分钟后 `torrent-get` 复查 `errorString` 应全空、`status` 0/1/6 均属正常。

## linuxserver 镜像会用环境变量重写配置文件（改 `settings.json` 等于白改）

`lscr.io/linuxserver/*` 这类镜像启动时读 compose 的 `USER`/`PASS` 等环境变量，**把 `settings.json` 重新生成**。症状极具误导性：`sed`/`jq` 改完 `rpc-authentication-required: false`，`docker kill` + `start` 之后读回来又是 `true`、`rpc-password` 又变回 49 位密文 —— 不是改错了文件，是**被启动流程覆盖了**，怎么改都会被打回。

- 要改这类设置：改 **compose 的环境变量**再 `docker compose up -d --force-recreate`，不要改 `settings.json`。
- **RPC 明文密码就在 compose 环境变量里**（`docker inspect <c> --format '{{range .Config.Env}}{{println .}}{{end}}'` 找 `USER`/`PASS`）；`settings.json` 里的 `rpc-password` 是 `{` 开头的密文，拿它当密码必 401。
- 改配置的文件操作一律 `docker exec`（容器内是 root），别用宿主账号碰 root 属主的 `settings.json`（`Permission denied`）。
- **拿不到 RPC 就什么都验证不了**：优先从环境变量拿凭据走 RPC，而不是反复折腾「关认证」——那条路在这类镜像上走不通。

## MP 下载侧把路径拆成子目录 → 辅种找不到 → 重复下载

qB 顶层 `save_path=/Media/未整理` 正确，但 MP 目录配置里 `download_category_folder=true` 会让**新建任务**落到 `未整理/<分类>/`（华语电影、电视剧…）。后果：IYUU/转移引擎按顶层约定对不上文件 → 判定「本地缺失」→ **重新下载一份**，Tr 里出现同名同 hash 双任务、共享同一目录的文件。

- **开关在 MP 目录配置**（MCP `query_system_settings` key=`Directories`）：只把 `download_category_folder` 改 false；`library_category_folder` / `library_type_folder` 保持 true（入库分类是对的），`download_path` 仍 `/Media/未整理`。
- **改它用 MCP `update_system_settings`，`operation` 参数必须省略** —— 传 `operation:"set"` 报「不支持的操作: set」，省略即默认 replace；`value` 是**整份 list 整体替换**，先 query 拿全量、只改目标字段再整份回写，别只传增量。
- 改完核对 qB：`save_path=/Media/未整理` 且 categories 为空。**已产生的子目录不用急着搬**：其种子已在客户端里，按 hash 能找到文件，受影响的只有新任务。
- **清理重复任务**：Tr RPC `torrent-remove {"ids":[重复id], "delete-local-data": false}` —— 双任务常共享同一路径的文件，删种子绝不能带删数据；**谁是原件看标签**：带 `转移做种` 标签的是转移原件，无标签且 `uploadRatio>0` 的是重复下的那个。

## 三个工具的分工与配置

| 角色 | 工具 | 关键配置 |
|---|---|---|
| 撤源 | MP 插件 `QbCommand` | `pause_cron` / `resume_cron` + `downloaders=[下载器名]` |
| 转移 | MP 插件 `TorrentTransfer` 或 IYUU `iyuu:transfer` | 源/目标下载器、路径映射、删源、启动/暂停 |
| 辅种（另一件事） | IYUU `iyuu:reseed` | 与转移共用 `cn_client`，但 cron 分开 |

### QbCommand（MP）两个必踩的语义坑

- **`pause_cron` 暂停的是「所有任务」**：注册时 `func=pause_torrent` 且 `kwargs={}`，`type` 取默认 `ALL` → **正在下载的任务也会被暂停**。这是把「严格固定延迟」换来的代价，规划时间点时按最坏情况（下载中断 1 小时）评估，靠 `resume_cron` 收尾。
- **`onlypauseupload` 不是状态过滤器，是一次性开关**：配置保存时 3 秒后 `date` 触发一次 `pause_torrent(type=UPLOADING)`，随后把该字段写回 `false`。想「每天定时只停做种」它做不到；它只用于「立刻停一轮」。
- `TorrentType`: `ALL=1 / DOWNLOADING=2 / UPLOADING=3 / CHECKING=4`。

### IYUU `iyuu:transfer` 的 `cn_crontab.parameter`

```json
{"from_clients":"1","to_clients":"2","marker":"tag","path_convert_type":"replace",
 "path_convert_rule":"/Media{#**#}/Media",
 "delete_torrent":true,"paused":false,"skip_check":false}
```

- **路径规则分隔符是字面量 `{#**#}`**（源码 `TransferServices::Delimiter`），每行一条 `from{#**#}to`；**WebUI 输入/显示却写 `@split`**（前端转换）。手工改库时按库的格式写，改完刷新页面确认显示成 `/Media@split/downloads`。
- `path_convert_type`: `eq`（相等，不转换）/ `sub` / `add` / `replace`。**两个客户端前缀不同时必须用 `replace`**，`eq` 会让目标拿着源路径去找文件。
- `delete_torrent=true` 才删源做种；`paused=false` 表示转移后**立即**启动目标（配合上面的延迟即可，不要依赖别的插件再 start 一次）。
- **`cn_client.torrent_path` 必须填**（qB 用 `/qb` 指向其 `BT_backup` 挂载）：IYUU 靠它读 `<hash>.torrent`，为空时报「种子文件不存在」直接失败。`seeding_after_completed` 只影响辅种，与转移无关。
- **路径不只存在 `cn_crontab.parameter`**：`cn_reseed.directory`（辅种记录，实测 11 条全是旧前缀）和 `cn_transfer.directory` / `convert_directory` 同样带路径。统一前缀时必须一起 `UPDATE`，否则辅种任务下一次运行又把旧前缀写回种子。改完整库扫干净：对 `cn_reseed`/`cn_transfer`/`cn_folder`/`cn_crontab`/`cn_client` 的每个 varchar/text 列跑 `COUNT(*) … LIKE '%/旧前缀%'`，**全 0 才算完成**。
- **改配置走 SQL 前先备份表**：`CREATE TABLE cn_crontab_bak_<tag> AS SELECT * FROM cn_crontab;`（`cn_client` 同理）；更省事是 `mysqldump -uiyuu iyuu <表…>` 落到宿主可写目录。IYUU 登录页有图形验证码，agent 进不去 WebUI 时改库是唯一路径；改完让 WebUI 刷新核对显示值。
- IYUU 的 crontab `target` 只有 `iyuu:transfer` / `iyuu:reseed` / `iyuu:rss` 三种，**没有 start/pause 命令** —— 想在 IYUU 内做「延迟后启动」是不可能的，必须借 QbCommand 的 cron 或客户端自身的状态机。

### MP `TorrentTransfer` 的对应字段

`frompath`/`topath` = 「源/目的数据文件根路径」（留空不转换）；`fromtorrentpath=/qb`（同 IYUU，读种子用）；`deletesource`；`autostart`（校验完自动 start）；`cron`。日志在 `/config/logs/plugins/torrenttransfer.log`（插件有独立日志，主日志里只有触发记录）。

## 验证链路（读回真实状态，不要只看日志）

三个客户端的 API 各有各的脾气，用错时返回的是 HTML 或 403，不是 JSON：

- **qB 5.x 不吃 Basic Auth**：先 `POST /api/v2/auth/login`（form `username/password`）拿 cookie SID，后续请求带 cookie。用 NAS IP 而非 `127.0.0.1`（agent 容器里的 loopback 不是 NAS）。
- **Transmission 4.x RPC 在 `/transmission/rpc`**：根路径 `/rpc` 返回的是第三方 WebUI（TrguiNG）的 HTML。RPC 要处理 `409` 握手（响应头 `X-Transmission-Session-Id`，带同一 header 重发）。
- **qB 路径配置有两套字段，且退出时整体回写**：活的是 `Session\DefaultSavePath` / `Session\TempPath`；`Downloads\SavePath` / `Downloads\TempPath` 是旧版遗留，qB 同样持有并回写。**qB 在退出时把内存配置整体写回磁盘** —— 运行中改完再 `docker restart`，退出那一下就覆盖掉你的修改（现象：改了读回是新值，重启后又变回旧值）。正确顺序：`docker stop` → 此时 `docker exec` 不可用，改用 `docker cp` 取出改好再 `docker cp` 写回 → `docker start` → 复读确认未被覆盖。
- **内网请求必须绕过代理**：`urllib.build_opener(ProxyHandler({}))`，否则请求被塞进 mihomo 返回空/非 JSON；`curl` 加 `--noproxy '*'`。环境里若有 `HTTP_PROXY`/`ALL_PROXY`，Python 脚本会默认继承——这是「脚本突然 Connection refused 而 curl 正常」的头号原因。
- **核验清单**：源任务数归零 + 源种子目录无残留（`BT_backup` 只剩 `queue`）→ 目标 `percentDone=1.0` + `save_path` 是映射后的前缀 + `error=0` → `status=SEEDING` 且 `uploadSpeed>0` → 宿主机 `find <媒体库> -links +1` 仍是硬链接、`-xtype l` 零断链。
- 目标已转移成功但被站点拒绝时，**不要删掉重来**：任务留在目标里，等站点超时后 start 即可，重转只会重演同一错误。
- `torrent-get` 返回的数字 `status`：**6 = SEEDING（做种中），不是停止**（0 才是 stopped）。`torrent-start` 返回 success 但数字「没变」，多数因为它本来就在跑；判死活看 `error` / `rateUpload` / `peersConnected`，`error=0` 且暂无 peer 属正常，别对着 6 反复 start。

## 「种子没自动转移」→ 先查转移引擎死活，再手动补跑

完成的种子一直没被转去保种、目标下载器没有新增，**头号原因是转移引擎容器 Exited**——它停摆期间错过的班次不会补跑也不报警，只留在任务表里。

1. `docker ps -a` 看转移引擎（实例 `iyuuplus-mm`）；`Exited` 即真凶。
2. 读任务与上次执行（容器内 socket 连 MySQL，root 密码若改过在 compose environment 里）：
   ```sh
   docker exec iyuuplus-mm sh -c 'mysql -uroot iyuu -e "select crontab_id,title,rule,target,enabled,from_unixtime(last_running_time) last from cn_crontab\G"'
   ```
   `rule` 是标准五段 cron（实例两任务都是每天 `0 12 * * *`，title `辅种` / `qb到tr`）；`last` 与当前时间一对照就知道错过了几班。`enabled=0` 的任务不会跑。
3. `docker start <c>`（restart 策略本来就是 unless-stopped，无需改）。**启动头约 1 分钟 PHP 会在 mariadb 就绪前刷 `SQLSTATE[HY000][2002] Connection refused` / `No such file`——这是启动竞态不是故障**，日志出现 `Success 载入计划任务，ID …` 即已恢复，别照着报错去修数据库。
4. 不等下个周期，容器内命令行手动补跑（**控制台入口，WebUI 有图形验证码 agent 进不去，改库和跑任务都走这里**）：
   ```sh
   docker exec iyuuplus-mm php /iyuu/webman iyuu:transfer <crontab_id>   # 参数 = cn_crontab 主键，本例 2
   docker exec iyuuplus-mm php /iyuu/webman iyuu:reseed <crontab_id>     # 辅种同理
   ```
   正常输出逐种子列 `存在种子：/qb/<hash>.torrent` → `成功推送种子到下载器`（`/qb` 即 cn_client.torrent_path 指向的 BT_backup）。
5. 验收：目标数量对上且 `status=6`，**几分钟后复查 `error=0` / `lastAnnounceSucceeded=true`**（补跑撞上站点「同位置」窗口的拒绝处理见上文两段式——大批量补跑先 pause 源）；源 `BT_backup` 只剩 `queue`（`delete_torrent=true` 删源是设计，别当丢数据）。
6. 引擎恢复后它会照 `rule` 自动跑；**转移引擎同时只能启用一个**（MP `TorrentTransfer` 与 IYUU 二选一）。MP 若配了 QbCommand 每日暂停窗口（实例 11:00 暂停 / 12:30 恢复），窗口内源下载器显示「暂停」属设计行为，不是故障。

## 归因：「谁转的？标签谁打的？」先查表，别信印象

两套转移引擎并存（MP `TorrentTransfer` 与 IYUU `iyuu:transfer`），「没自动转移 / 没打标签」按这张表定性，查完再动手：

| 观测 | 结论 |
|---|---|
| `cn_transfer` 有该 hash 行（主键 `transfer_id`，**没有 `id` 列**，`order by id` 会报错） | IYUU 转的（手动补跑也算） |
| 目标端带 `转移做种` 标签，且 MP 日志有 `转移做种服务` 注册/触发记录 | MP 插件转的（标签来自其 `add_torrent_tags` 配置） |
| 源端种子仍在、两边库都无记录 | 两班都没跑成 → 回上一节查引擎死活 |

- **`cn_crontab.running_count` 计的是「任务成功跑过几次」，空跑照样 +1** —— running_count 大而 `cn_transfer` 没几行，只说明班次跑过、无货可转，**不是「转移成功过 N 次」的证据**。
- **标签是两套互不相干的语义**：MP 端 `add_torrent_tags` 配什么打什么（实例 = `转移做种`）；IYUU 端由 `cn_crontab.parameter.marker` 决定——缺省/`empty` = 不打标，`tag` = 打 `IYUU自动转移`（源码 `'IYUU'.ReseedSubtypeEnums::text(Transfer)`，**名字写死，永远不等于 `转移做种`**）。开启/修改：`UPDATE cn_crontab SET parameter=JSON_SET(parameter,'$.marker','tag') WHERE crontab_id=<id>`（键不存在也会新增，运行时读库、当班生效）。
- **补历史欠账**（已转但没标签的）：Tr RPC `torrent-set {"ids":[...],"labels":["转移做种"]}` 一次性补齐；**不要为此改引擎代码**——容器重建即丢。
- **判 MP 插件是否启用要跨日志轮转查**：`grep -n '注册插件服务(自动转移做种)\|移除插件服务(自动转移做种)' /config/logs/moviepilot.log*`——**注册只发生在 MP 启动/重载时**，当日日志没有注册行 ≠ 停用（轮转后本来就看不到），移除行晚于最后一条注册行才算停用。

## 已有数据 + 用户给的种子 → 补挂做种（正向流程，不重下）

文件已完整躺在盘上、用户把 `.torrent` 发来了，按序执行，**每步都是上一步的闸门**：

1. **解析**：`python3 scripts/parse_torrent.py <x.torrent>`（本 skill，零依赖）→ 核对 infohash、总大小、集数与磁盘一致；`private=1` 的 announce 自带账号 passkey，**种子文件与 announce 不外发**（脚本输出里 passkey 已打码）。多文件种子的落盘规则是 `<download-dir>/<info.name>/…`。
2. **对路径（recheck 前的唯一闸门）**：宿主机 `ls` 数据目录，**文件夹名与种子 `name` 逐字节相等**再继续；不等就先统一，别赌校验（败了就是整包重新下载，分诊见 `media-pipeline-paths.md`「校验中→变成下载」）。
3. **暂停态推入**：RPC `torrent-add {metainfo: <base64 整个种子文件>, paused: true, download-dir: <父目录>}`——先 paused，路径错了也不会开下；大种子走 RPC base64 直推，不必传进 NAS（这台 NAS scp 不可用）。
4. **校验**：`torrent-verify` → 轮询 status：**1/2 = 校验中**（264G 约 20–40 分钟，HDD 150–250MB/s）；**status 变 4 = 路径没对上、正在重新下载 → 立刻 `torrent-stop` 排查**，绝不放任。`percentDone` **校验期间就显示 1.0**，完成与否只看 status 回 0；要证明「一直在校验」不是卡死：宿主机双采样 `/proc/diskstats`（隔 3 秒读同一盘 sectors read，差值 ×512 ÷ 3s ≈ 读速），持续上百 MB/s = 真在读盘，ETA ≈ 种子大小 ÷ 实测读速。
5. **开种**：`torrent-start` → status=6，复查 `error=0` 收工。
