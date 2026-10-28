# NAS Administration — UGREEN DXP4800 & Jellyfin

## UGREEN DXP4800 Specifics

- **SSH user**: Use `user` (not `root`) — root SSH disabled by default. Password = `<PASSWORD>` (same as PVE)
- **user is in `docker` group since 2026-10-01** — `docker ps`/`docker logs` work directly (added via interactive sudo + usermod)
- **SCP does NOT work** — fails `No such file or directory` even for valid dirs. Transfer via: `cat local.file | sshpass -p PASS ssh USER@IP 'cat > /dest/path'`
- **sudo needs password; never pipe to `sudo -S`** (Hermes guard blocks it) — use interactive pty: `terminal(pty=true, background=true)` + `process_manage submit`
- **OS**: Debian 12 (bookworm), kernel 6.12
- **Jellyfin**: 当前是 docker 容器 `jellyfin`（`docker ps` 实测）。**先 `docker ps --filter name=jellyfin` 确认再选重启方式**：容器在 → `docker restart jellyfin`；确实没有容器才用旧形态的裸进程 `kill JELLYFIN_PID` → auto-restarts。容器只挂载 `/home/user/movie/film→/media/films`、`/home/user/movie/tv→/media/tvseries`、`/home/user/Music→/media/music`，**挂载外的路径 Jellyfin 一律看不见**。
- **Jellyfin DB**: `/volume1/docker/jellyfin/config/data/jellyfin.db`
- **MusicTagWeb**: UGREEN NAS app (not Docker container)

## ⚠️ UGOS 私有 ugacl xattr：容器内非 root 写不了 bind mount（777 也没用）

**Symptom (2026-10-01, iyuuplus/MariaDB case):** inside a docker container on the NAS, EVERY non-root uid gets `EACCES` writing a bind-mounted dir that `ls` shows as `drwxrwxrwx`, and — the smoking gun — **non-root `stat()` reports the same inode as mode 000 while root sees 777** (per-caller st_mode! PHP `fileperms`/busybox `stat` both confirm, stable, order-independent). Host non-root users (user) work fine; container root works fine. MySQL (`mysqld --user=mysql`) crash-loops with `Can't create/write to file './ddl_recovery.log' (Errcode: 13)` → app login dies with `SQLSTATE[HY000] [2002] No such file or directory`.

**Root cause:** UGOS Pro's proprietary ACL stored as **`system.ugacl_self` xattr** (plus `ug.archive_bit`, `ug.archive_version`, `user.ug.flags`). Windows-style ACEs, enforced by the UGOS kernel — it computes EFFECTIVE permission per caller from the ACE list and reports THAT as st_mode (hence per-uid stat). ACEs on the iyuu dirs were `group:admin / group:admin1 / owner(=ACL owner user) / user:user` — container uid102 matched NOTHING → default deny 000. It OVERRIDES POSIX mode bits entirely.

**Inspect:**
- `sudo /usr/bin/ugacltool stat <path>` → decoded ACEs (owner, entries, inode, mode)
- `sudo ugacltool get <path>` → ACE list; `getace` → "It's Linux mode" means plain POSIX enforcement is active
- `getfattr -n system.ugacl_self --dump <path>` → raw blob (BACK THIS UP first: `0sAQAAAAoA...`)
- Help: `ugacltool` (add/addace/replace/get/getace/del_one/del_all/copy/check/stat); `ugaclstatus.sh <mountpoint> <enable|disable>`

**Fix that worked (container mysql needs uid102 write on `iyuuplus/data`):**
1. `sudo getfattr -n system.ugacl_self --dump <path> > backup.txt` (save blob — getfattr restore value = whole `0s...` string)
2. `sudo setfattr -x system.ugacl_self <path>` (remove) — ⚠️ immediately makes the dir DEFAULT-DENY for everyone non-root (host user loses write too!)
3. `sudo setfattr -n system.ugacl_self -v '0s<backup-blob>' <path>` (restore the exact bytes)
4. **`sudo chmod 777 <path>` — THE TRIGGER.** Without this the kernel keeps the old state; chmod forces re-evaluation and enforcement drops to plain POSIX mode (`getace` → "It's Linux mode"). Verify: container non-root sees 777 + writes OK; host user writes OK.
5. `docker restart <container>` → mysqld starts normally.

**Alternative (untested format):** `ugacltool addace <path> '<ACE>'` to GRANT uid102 instead of falling back to POSIX — ACE display form: `user:NAME:allow:rwxpdDaARWc--:----`.

**Caveat:** enforcement is currently Linux-mode fallback; if a UGOS service re-attaches the ACL later the symptom may return — re-run the chmod trigger or check `ugacltool stat`. Only dirs WITH the xattr are affected (check with `getfattr -n system.ugacl_self`; on the mp-v2 stack only `iyuuplus/iyuu` and `iyuuplus/data` had it).

**Diagnosis battery that finds it fast:** root vs non-root `busybox stat -c %a <path>` in container (different values = ugacl) → `getfattr -d` for `system.ugacl_*` → root/non-root/host write matrix → rule out apparmor (`docker run --entrypoint sh --security-opt apparmor=unconfined`, still fails ⇒ not apparmor) → errno is 13 not 122 ⇒ not quota.

## iyuu Plus 登录/密码重置

- 登录页 `http://<NAS>:8787`，账号 `ugreen` / 密码 `Ugreen111`（2026-10-01 重置；DB 来自压缩包，源机器 2025-12-07 的旧哈希导致「密码错误」）
- 登录接口：`POST /app/admin/account/login`，表单字段 `username/password/captcha`，验证码 cookie 名是 **PHPSID**（非 PHPSESSID），session 文件在 `/iyuu/runtime/sessions/session_<sid>`，内容 PHP 序列化格式 `s:13:"captcha-login";s:4:"xxxx"` —— 可脚本化完整登录验证
- 重置密码：容器内 `NEWHASH=$(php -r 'echo password_hash("新密码", PASSWORD_BCRYPT);')` → `mariadb -uiyuu -piyuu -Diyuu -e "update wa_admins set password='$NEWHASH', updated_at=now() where username='ugreen'"` → 用 `password_verify` 回验
- **⚠️ 改 IYUU_TOKEN 后页面永远显示空 = 已保存但没热加载（2026-10-01）**：`ConfigController::update` 写 `/iyuu/.env` 成功（`is_iyuu_token` 正则：len<60 + 以IYUU开头 + 首个T位置<15），但 webman 只在**启动时**用 Dotenv 加载 .env（`support/bootstrap.php:45`），`update_env_value` 不 putenv → 运行时 `env('IYUU_TOKEN')` 仍是旧值 → 页面看起来「配置不上」。**修复 = `docker restart iyuuplus-mm`**，以后凡 iyuu_config 区的改动（token/ipv6/cloud）保存后都要重启容器。验证：登录后 GET `/app/admin/config/get`（响应是裸 config 对象，无 code/data 包裹），看 `iyuu_config.iyuu_token` 长度
- 配置读取接口 `GET /app/admin/config/get`、保存 `POST /app/admin/config/update`（自动路由）

## MoviePilot 管理与整理管线（2026-10-01 实战验证）

- **MP 登录密码重置**：zip 带的 PGSQL 里有源机器账号，compose 的 SUPERUSER_PASSWORD 只在首次初始化生效。重置：用户表叫 **`user`**（字段 name/hashed_password，不是 users/username）；在 moviepilot 容器里 `python -c "from passlib.hash import bcrypt; print(bcrypt.using(rounds=12).hash('pw'))"`（$2b 格式 MP 认）；psql 写入必须用**内嵌 heredoc**（`psql <<'SQL' ... SQL`）——哈希里的 `$` 会被 shell 展开毁掉（实测存成垃圾）。**嵌套更深时（ssh → docker exec → psql，带中文/SQL 引号/双引号表名）直接把整个远端脚本 base64 化**：本地 `b64 = base64.b64encode(script).encode()` → `echo <B64> | base64 -d | bash`（最外层只留一层 `shlex.quote`），脚本内部照常写 SQL 与中文 —— 判断信号是命令里出现两层以上引号嵌套时，继续拼引号一定会炸语法。
- **JWT**: `POST /api/v1/login/access-token` 表单 username/password。**注意**：终端输出会把 JWT/密钥脱敏成占位符，拿 token 后直接写文件用，别经输出。
- **目录配置**在 mp-pgsql 的 `systemconfig` 表 key=`Directories`，zip 已预配好目标管线：`download_path:/Media/未整理, monitor_type:monitor, monitor_mode:fast, transfer_type:link(硬链接), library_path:/Media/已整理, scraping:true, renaming:true`。下载器在 key=`Downloaders`（qb=localhost:8888 host网络, trans=192.0.2.10:9091）。
- **E2E 实测**（2026-10-01）：往 `/volume2/downloads0/未整理/` 投一个片名规范的目录 → 15秒内完成 监控捕获→TMDB识别→link转移到 `/Media/已整理/外语电影/盗梦空间 (2010)/` → 刮削下海报/clearart/logo → 发通知。**源与目标 inode 完全相同（5243253），links=2 = 真硬链接零拷贝**。前提是未整理/已整理同在 volume2（跨卷不能硬链接）。
- **坑：fast 监控是 inotify 增量，不回填**——监控启动前就躺在未整理里的存量文件不会被自动整理，需手动：MP 网页手动整理多选，或 `GET /api/v1/transfer/now?token=<MP_API_TOKEN>`（verify_apitoken，从下载器侧拉已完成任务整理）或 `POST /api/v1/transfer/manual`（JWT，body: ManualTransferItem{fileitem:{storage,type,path},target_path...}）。
- 开机时监控目录若不存在会启动失败（Monitor.watchdog 每分钟自愈重启）；测试后记得删 transferhistory 表里的测试记录（src_fileitem::text like 匹配）。
- **MP 手动整理 API 坑（/api/v1/transfer/manual，JWT 走 login/access-token 表单，用 admin/<PASSWORD>）**：① 只支持单 `logid`（`logids` 复数仅供 preview/history 查询端点）；批量=逐文件循环 `fileitem:{storage,type,path}`+tmdbid+type_name。② **fileitem 模式 force=False：同源已有成功历史会静默跳过（API 仍返 success=true，不落盘不写新行）**——验收必须数磁盘文件，logid 模式才自动 force=True。③ **logid 模式会用历史 seasons/episodes 覆盖请求参数**：脏历史先 `update transferhistory set seasons=…, episodes=null`。④ **目录层级两个开关都要显式传 true**：`library_type_folder`(类型层 电视剧/电影) + `library_category_folder`(分类层 日番/欧美剧/动画电影)，漏一个就落顶层拆坏目录树；UI 默认都开。⑤ 收尾查历史：status=false 应只剩非媒体文件，整理过的旧失败行会自动消失。
- **TMDB 权威查询**：别信 MP `search_media` 首条（中文模糊会串台），直查 `api.themoviedb.org/3/search|tv|season` 走 Clash（MP 内置 key 在 /app/app/core/config.py: TMDB_API_KEY）。已验证映射：To LOVE-Ru 全系列=34742 一部剧(S00特别篇17集=OVA1-6+OAD7-16,S2=Motto,S3=Darkness,S4=Darkness2nd)；无耻之徒(US)=34307；间谍过家家=120089；星球大战3=1895；EVA新剧场版序/破/Q/终=15137/22843/75629/283566；HP1-8=671,672,673,674,675,767,12444,12445；复联4=299534；12.12首尔之春=919207；活着(张艺谋1994)=31439(注意 661950=2020同名外国片，用 ffprobe TAG title 看内嵌名分辨)。OAD/OVA 无集号解析时传 `episode_detail`（TMDB S00 号=源号偏移 OAD+6）。
- **目录类型层根治（2026-10-01）**：自动流落盘无“电视剧/电影”层的根因 = systemconfig `Directories` json 缺 `library_type_folder` 字段（默认 false；UI 手动整理则显式传 true）。修复：update systemconfig set value=$json$…$json$::json 加字段后重启容器。注意 `value` 列是 json 类型（left/length 需 ::text，否则静默报错）。整理完顶层分叉树：同卷 mv + SQL 同步 dest（replace 前缀，LIKE 限定防误伤）+ jellyfin 忽略不用管。验收 SQL：`dest not like '%已整理/电影%' and not like '%已整理/电视剧%'` 归零。
- **刮削**：POST /api/v1/media/scrape/{storage}，**鉴权用 header `X-API-KEY: <API_TOKEN>` 即可（verify_token 见到该 header 就按超级管理员放行，不需要 JWT）**，API_TOKEN 在 `docker exec moviepilot-mm cat /config/app.env`；**body 是 FileItem 本体** `{"path":"/Media/已整理/…","storage":"local"}` —— 包成 `{"fileitem":{…}}` 会被解析成 path="/"，日志出现 `识别媒体信息时未提供元数据名称` 且返回 `刮削失败，无法识别媒体信息`。同步耗时 60-120s/目录，**客户端超时空响应≠失败**（uvicorn 线程继续跑），短超时批量点火后直接验磁盘（目录内有 nfo/jpg 即成）；555个完成≈2分钟。自动整理批会触发整剧重刮，重启会丢排队中的刮削任务→事后用该接口补。**成功行也可能误判类型**（首尔之春→律界战争S01E12 这种跨类型错配），验收要对比 dest 合理性。删测试历史行前先确认文件已有其他成功行+dest 存在，否则断链变孤儿文件。
- **整理失败分析（2026-10-01 手动整理 782 文件：579成/203败，errmsg 全部=未识别到媒体信息）四类根因**：① 非媒体附属内容（VCB包 SPs/CDs 目录：NCOP/NCED/菜单/广播剧mp3，160个）→ 识别失败是正确行为；② 瞬时失败（批量高峰 TMDB 抖动，如 SPY×FAMILY 12个）→ 复测能识别，重试即过；③ 文件名解析硬伤：`Shameless.U.S.` 点缩写切碎成 "Shameless U S"、`Episode.III-` 的 III 被吃掉、EVA 全角：日文混排 → 解析标题过不了校验（但 search_media 直搜能出结果：无耻之徒=34307，星战3=1895）→ 用失败记录「重新整理+手动指定 TMDB ID」修；④ 诊断法：MCP recognize_media 复现单文件 vs search_media 直搜，隔离解析问题还是网络问题。
- **⚠️ 季冲突：识别对了剧却全落到 Season 1（"多季只整理出几季"的根因）**。
  MP 从文件名/父目录名解析季号，名字里没有 `S02`/`第2季`/`Season 2` 这类 token 时季默认=1、集号取文件里的 `[01]` → 同一 TMDB 剧的所有季度都指向 `Season 1/xx - S01E01..E12`，而 `overwrite_mode=always` 会先删已有文件再硬链接 → 后处理的季度覆盖先处理的，被覆盖的链接**直接消失**（源文件仍在未整理，nlink 回到 1）。判定：日志里同一目标路径反复出现 `目的文件系统中已经存在同名文件…正在删除已存在的文件`。修复优先级：① 手动整理时显式指定 tmdbid + 季集（落盘 Season N）；② 加识别词规则把季度名映射到季号（如 `Motto To LOVE-Ru → 第2季`）；**不要改源文件名**（源=做种文件，改名破坏 qB 校验）。特典/菜单（NCOP/NCED/Menu/CM/CD）被判"附加视频"不入库是**预期行为**，不是漏整理。
- **⚠️ 识别词（自定义识别规则）格式是 `原串 => 替换串`**（如 `Motto To LOVE-Ru => 出包王女 第2季`），落库在 `systemconfig.key=CustomIdentifiers`（json 列，重启不丢），MCP `update_custom_identifiers` 一次传全量数组。**子串匹配会串台续作**：`To LOVE-Ru Darkness => 第3季` 同样吃掉 `To LOVE-Ru Darkness 2nd`，续作会被送去第 3 季。铁律：`overwrite_mode=always` 下**每次 transfer 前、以及每次改完识别词后**，都用 `recognize_media`（只读）把同剧所有兄弟目录各过一遍，逐个核 `meta_info.begin_season`；只验目标目录等于没验——串台发生在你以为不会碰的那个目录，而改一条规则会悄悄弄坏你已经验过的另一条。
- **修串台靠「规则顺序」，不靠往替换串里加字符**：MP 按数组顺序依次替换，先命中的先生效 → 把最长/最具体的写在最前（`Darkness OADs` > `Darkness 2nd` > `Darkness` > `Motto`），短串自然吃不到续作。**别试 `To LOVE-Ru Darkness [` 这种带方括号的排除串**：MP 预处理会把 `[…]` 整段从标题里洗掉（`recognize_media` 返回的 `meta_info.name` 已是 `To Love Ru Darkness Ma10p`，方括号一个不剩），带 `[` 的规则永远匹配不上 → 结果是**目标季和续作一起失效**（`begin_season` 变 null），而不是只排除续作。加规则前先看返回的 `name` 字段长什么样，那才是匹配真正发生的字符串。
- **⚠️ 整理报「已整理过」= transferhistory 残留成功行，与磁盘无关**。先备份再删，且只删目标季的行（本季正常记录别碰）：`CREATE TABLE transferhistory_bak_<tag> AS SELECT * FROM transferhistory WHERE 1=0;` → `INSERT INTO … SELECT * … WHERE status=true AND src LIKE '%<目标目录>[%'` → `DELETE … 同条件`。⚠️ `status` 是 **boolean**（写 `status='成功'` 直接报 `invalid input syntax for type boolean`）；失败行 (false) 不挡路，留着无害。
- **⚠️ MP 的路径是容器命名空间，拿错不报错、只返空**：`list_directory`/`recognize_media`/容器内 `ffprobe` 用 `/Media/...`；宿主机对应路径查 `docker inspect --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' moviepilot-mm`（本机 `/volume2/downloads0 -> /Media`）。**成片的目录树/断链/链接数检查全空且 exit 0 = 路径错，不是文件丢了**——文件操作走宿主机路径，ffprobe 必须进容器用容器路径。
- **⚠️ `transfer_file` 没有 episode 参数**：只能给 `season`，集号靠文件名解析。`overwrite_mode=always` 下集号解析不出的文件（无 `[01]`/`E01` token）**别盲传**——会落到该季已占集号上覆盖正确文件；而改源名加集号被做种红线禁止 → 报给用户定夺。**用户答复「补上」时走手动补集，绕过 MP 识别链路**：① 先 `ffprobe` 核时长对上 TMDB 该集 `runtime`（文件名没有集号，时长是唯一能证明「这个特典就是缺的那集」的证据，别只看名字像）；② `ln <源> "<季目录>/<剧名> - S0XEXX - 第 X 集.mkv"`，命名跟同季其他集逐字一致，源与目标同卷才可硬链接，`links` 变 2 即成、零额外空间；③ 硬链接不写库，MP 会一直显示比磁盘少 1 集、下次对账又报缺集 → 补一条 `INSERT INTO transferhistory`（照抄同季现有成功行的全部字段：`src/src_storage/dest/dest_storage/mode/type/category/title/year/tmdbid/imdbid/seasons/episodes/status=true/media_source/media_id`，`date` 是 varchar 用 `to_char(now(),'YYYY-MM-DD HH24:MI:SS')`，套 `WHERE NOT EXISTS` 防重）；④ 补完记得补刮削（`scrape_metadata overwrite=false`），否则新集没有 nfo/图。硬链接绕过的是「SPs 目录判为附加视频不入库」那条过滤，源文件仍在未整理且 mtime 未变，monitor 不会把它重扫进别的季。
- **⚠️ 搜索整轮一条不回（日志反复 `未开启任何有效站点，无法搜索资源`）先查这两处，比查匹配上游**：① MCP `search_torrents` 的 `sites=[站名]` **不吃站点名** —— 传了等于一个站都没开，且返回里的 `all_sites` / `search_site_ids` 有回显 ≠ 真开了站；**不传该参数即默认搜全部 active 站**。② 站点 cookie 混入全角标点（网页复制常见，如 U+FF1B `；`）会让该站请求直接炸 → mp-pgsql 容器里清洗：`SELECT id,name,(cookie LIKE '%；%') FROM site;` 找中招的，再 `UPDATE site SET cookie=replace(cookie,'；',';') WHERE cookie LIKE '%；%';`。清洗属数据卫生，**修完必须重搜确认该站进了 `search_site_ids`** 才算恢复，别默认已好。
- **⚠️ 搜索「过程明明有、最后变空」= 两阶段，站点返回 ≠ 匹配通过**。MP 先并行打站点拿原始条数（渐进式流实时推给前端 → 用户看到的「有」），再用 `标题/原标题/别名` 逐条过滤，日志写 `匹配完成，共匹配到 N 个资源`；最终列表只显示匹配后的，N=0 就是界面突然空掉的全部原因，不是「站点没搜到」。
  - **取证**：应用日志在 `/config/logs/moviepilot.log`（注意 `logs` 复数，不是 `/config/log`），grep `关键词|匹配完成|搜索完成，共` —— 一行就给出 `标题/原标题/别名` 和每个站的 `返回数据：N`，直接区分「没搜到」和「搜到被过滤」。
  - **复现取标题**：MCP `search_torrents`（带 `douban_id` 或 `tmdb_id`）→ `get_search_results` **必须带 `page`**，否则只返回 `total_count` + `filter_options`、没有 `results[]`，看起来像「没有结果」。`filter_options.site` 只列有匹配的站，是最快的单站有效性判断。
  - **根因按序排查**：① 站点拿**中文关键词**搜，而资源标题是**英文原名**（华语片在 PT 站常挂英文发行名，属正常、不是匹配错片）→ 只能靠 `别名` 兜底，命中时日志写「通过别名或译名匹配到资源」；② `原标题` 为空（豆瓣只有「又名」进别名，没有英文原名字段）→ 缺主匹配串；③ **某站 1 秒回几十条 = 泛匹配/热门兜底**，不是该片资源，全会被过滤；④ 个别站点对中文标点抛 `ascii codec can't encode` → 该站整轮直接跳过。
  - **IMDb 输入不算错**：日志出现 `ttNNNNNNN` 即 IMDb 被识别，MP 随后转豆瓣 ID 走搜索；豆瓣条目的 IMDb 字段回指同一 tt 号即转换正确 —— 别把「走 douban」当成用错链接。
  - **站点返回不稳定**：同关键词隔几分钟结果数会变，重搜 2~3 次再下结论；排查期间**不要动识别词**（匹配失败与识别词无关，改它只会引入新故障）。
- **审查用外部真值对账，且一次性给完整报告**：每季集数与 `query_media_detail(tmdb_id, media_type=tv).season_info` 的 `episode_count` 逐季对（含 S0 特别篇，最容易漏）；`find -printf '%n'` 验 mkv 全是 n=2、`find -xtype l` 验零断链、`ffprobe duration` 抽样验正片（~1400s）不是特典（几十秒）。用户不在时，把「缺哪集 / 哪条识别词有副作用 / 哪些未刮削 / 哪些非视频误入」连同处置建议一次写完，不分轮抛问题等回复。
- **⚠️ 判断"哪些真没整理"必须用 inode/nlink，不能肉眼数未整理里的文件**。link 模式下源文件永远留在未整理，用户会因此误判"很多没被整理"。核验配方（未整理/已整理须同卷，跨卷无法硬链接）：
  ```bash
  cd /volume2/downloads0
  find 未整理 -type f \( -iname '*.mkv' -o -iname '*.mp4' \) -links +1 -printf '%i\n' | sort -u > /tmp/a
  find 已整理 -type f \( -iname '*.mkv' -o -iname '*.mp4' \) -printf '%i\n' | sort -u > /tmp/b
  comm -23 /tmp/a /tmp/b   # 必须为空：已链接却在库里找不到 = 发生过覆盖丢失
  # 真正没入库的 = 未整理里 nlink==1 的文件，按其顶层目录归组即可看出缺了哪几季
  ```
- **⚠️ 整理 ≠ 刮削，且刮削队列是建队时的快照**。批量识别/刮削任务按每条约 60s 顺序吃**建队那一刻**的目录清单，队列建好之后新整理的条目永远不会被补刮（表现：目录里只有视频、没有 .nfo/poster/fanart）。用 scrape 接口逐目录补，成功判据=磁盘上出现 `.nfo` + `poster.jpg`（fanart/backdrop/logo 视片源而定）。
- **⚠️ Jellyfin 看不到已整理**：MP 的 library_path 是 `/volume2/downloads0/已整理`，而 jellyfin 容器挂载列表里没有这个路径 → 整理得再完整 Jellyfin 也刷不出来。`mediaserveritem` 表里 `/media/tvseries/…` 老路径的行是陈旧记录，同步时会自动清。**修法要动容器，先征得用户同意**：给 jellyfin 加挂载 `/volume2/downloads0/已整理 → /media/library` → 重建容器 → 库指向新路径。
- **⚠️「MP 账密进不去」先三步取证再谈重置（2026-10-02）** —— 目标是先证明"服务端密码到底变没变"，再决定怪谁：
  1. **哈希回验**：psql 取 `hashed_password`（⚠️ `user` 是保留字，SQL 必须写 `"user"`；该库 `value` 列是 json，`left/length` 要先 `::text`），在 moviepilot 容器里用 passlib 回验候选，明文走环境变量不进 argv：`docker exec -i -e H='<hash>' -e C='["候选A","候选B"]' moviepilot-mm python -c "import os,json;from passlib.hash import bcrypt;print([i for i,x in enumerate(json.loads(os.environ['C'])) if bcrypt.verify(x,os.environ['H'])])"`。passlib 打印的 `bcrypt version` AttributeError 是无害噪声，看最后的命中列表；⚠️ 别用 `%` 格式化拼带 `HTTP=%{http_code}` 的 curl 串（`%{` 被当格式符直接抛 `unsupported format character`），嵌套 ssh+docker exec 的环境变量要 `shlex.quote` 逐层引用。
  2. **本机真实登录**：`curl -X POST http://127.0.0.1:3000/api/v1/login/access-token --data-urlencode username=admin --data-urlencode password=<候选>` → 200 + `access_token` = 服务端可用。
  3. **谁发的错误密码**：`docker logs moviepilot-mm --since 30m | grep login/access-token` 直接给出 401 的**来源 IP**；配应用日志 `user.py - 用户 admin 通过密码认证成功 / 密码验证不通过` 对时间线（应用日志无 IP，access log 无账号，两个都要看）。
  **判据**：本机 200 + 用户设备 IP 401 ⇒ 密码根本没被改，是浏览器/密码管理器自动填充了旧密码 → 让他手敲一遍并重新保存，**不要急着重置**（重置后他记住的又对不上，还掩盖真问题）；只有本机也 401 才走上一条的重置流程。
- **⚠️ 绑定站点报「客户端未查询到站点数据」= 本地 cn_sites 表空（2026-10-01）**：绑定校验 `Site::uniqueSite()` 查本地 `cn_sites`，而页面上的站点列表来自远程推荐接口——两边数据源不同。安装 SQL 只建表不带数据，这张表唯一填充方式是「同步站点」（`SitesServices::sync` → `http://2025.iyuu.cn/reseed/sites/index`，需有效 IYUU_TOKEN，国内直连秒回200）。博主封装包首次必坑。修复：登录后 `POST /admin/site/sync`（注意是 `/admin/...` 不是 `/app/admin/...`，app级控制器路由无 /app 前缀；页面同步按钮就是这个 URL），验证 `select count(*) from cn_sites` → 104行。

## MoviePilot v2 deployment (`/volume1/docker/mp-v2`, 5 containers)

Stack: moviepilot-mm (host net, web :3000/:3001), mp-pgsql-mm (:55053), mp-redis-mm (:55054), qbittorrent-mm (host net, :8888), iyuuplus-mm (:8787). Compose: `/volume1/docker/mp-v2/docker-compose.yaml` (CRLF line endings — edit with awk, sed `a\` quoting breaks). Login: admin/<PASSWORD>（2026-10-02 验证：容器内 bcrypt 回验匹配 + `POST /api/v1/login/access-token` 返 200；旧的 admin/password 已失效）。

**⚠️ PITFALL: MP 2.15.6 entrypoint unconditionally runs `python -m cloakbrowser install` — a 217MB GitHub Releases download — and web UI (port 3000) does NOT start until it finishes.** NAS traffic is intercepted by router OpenClash transparent proxy → GitHub crawls ~32KB/s → container stuck `unhealthy`, port 3000 never opens (symptom: mp 打不开 but qb fine; `docker logs moviepilot-mm` shows `Downloading from https://cloakbrowser.dev/...`).

**Fix (permanent) — set `CLOAKBROWSER_BINARY_PATH` env in compose:**
1. Download `cloakbrowser-linux-x64.tar.gz` on Hermes/PVE host (35-40MB/s — PVE host is NOT transparent-proxied, NAS is) from `https://github.com/CloakHQ/cloakbrowser/releases/download/chromium-v<ver>/cloakbrowser-linux-x64.tar.gz`
2. Cat-pipe to NAS, extract to `./moviepilot-v2/config/cloakbrowser/` (persistent /config mount; tar layout is FLAT, `chrome` at root), chmod +x chrome/chromedriver
3. Add `- CLOAKBROWSER_BINARY_PATH=/config/cloakbrowser/chrome` to moviepilot env → `docker compose up -d` → log shows `Using local binary override` → UI up in ~2.5 min
4. Keep the tarball at `/volume1/docker/mp-v2/` as offline backup

**MP external connectivity**: MP only honors `PROXY_HOST`. **⚠️ THE ACTUAL CULPRIT (found via MP's in-app 连通性测试): `/etc/openclash/custom/openclash_custom_rules.list` has `SRC-IP-CIDR,192.0.2.10/32,DIRECT` (+ .248) near the TOP** (custom rules are prepended; comment says 设备绕过代理) → ALL NAS-sourced traffic matches it BEFORE any domain rule → MP on the NAS can never reach TMDB/TVDB/Telegram/githubusercontent/codeload. This ALSO explains the cloakbrowser 32KB/s: explicit proxy → SrcIPCIDR → DIRECT GitHub. **Adding domain rules to the config yaml does NOT help for NAS sources** (they land at the bottom). Fix: insert, ABOVE the SRC-IP-CIDR lines in that custom list (indent `  - `): `DOMAIN-SUFFIX,themoviedb.org,SSRDOG`, `DOMAIN-SUFFIX,thetvdb.com,SSRDOG`, `DOMAIN-SUFFIX,telegram.org,Telegram`, `DOMAIN-SUFFIX,githubusercontent.com,SSRDOG`, `DOMAIN-SUFFIX,codeload.github.com,SSRDOG`, `DOMAIN-SUFFIX,github.com,SSRDOG`, `DOMAIN-SUFFIX,bgm.tv,SSRDOG` — **github.com MUST be listed too**: without it, MP's github.com test times out (ReadTimeout 10s) AND codeload fails too (its 301 redirects to github.com; the second hop dies). Direct github.com from the router is intermittent — curl may pass while httpx times out minutes later, so verify with MP's own stack (httpx in container), not just curl. **bgm.tv (Bangumi) is GFW DNS-poisoned**: resolver returns Facebook IPs (31.13.x / face:b00c::) → instant ConnectError on EVERY path incl. direct; real IPs are overseas (DoH `dns.alidns.com/resolve` to see truth). Fix = same pattern: `DOMAIN-SUFFIX,bgm.tv,SSRDOG` (covers api./lain. subdomains) in the custom list AND before MATCH in the active yaml (non-NAS devices). MP's bangumi module uses `https://api.bgm.tv/` — there is NO bangumi entry in the MP nettest list; a user reporting 「bangumi连接不上」 means the bangumi module/media-search source, tested via `docker exec … httpx /v2/subjects/350235`. Backup both files, `/etc/init.d/openclash restart`, then verify **from NAS source**: `curl -x proxy https://api.themoviedb.org/3/movie/550` → **401/301 = OK, 000 = still broken**, plus gstatic 204 for general proxy sanity. Subscription refresh may overwrite the yaml — re-check after sub updates. Diagnosis tool: Clash API `/rules` (ordered!) shows exact match order; `/connections` shows live chains.

Clash API: `http://192.0.2.10:9090`, secret `<PASSWORD>` (grep in `/etc/openclash/*.yaml`). `/connections` shows live chains incl. matched rule — best tool to prove which rule/node a domain takes.

**MP MCP (让 agent 接入)**: stateless JSON-RPC endpoint `POST http://192.0.2.10:3001/api/v1/mcp` (backend port :3001, host network; no SSE — probe with curl `initialize` before wiring). Auth = `X-API-KEY` header; key lives in `~/.hermes/config.yaml` → `mcp_servers.moviepilot`. 77 tools exposed; MP hides `execute_command`/file ops/`search_web` server-side. Wired into Hermes compressor-wrapped (config pattern in the `native-mcp` skill): 77 tools → 3 meta-tools `moviepilot_list_tools` / `moviepilot_get_tool_schema` / `moviepilot_invoke_tool`; invoke signature = `tool_name` + `tool_input` (+ `quiet`/`toonify`)，且必须包在外层 `arguments` 里 —— 把 `tool_name` 放到 calls 条目外层会报 `missing required argument(s): tool_name`（与 HA MCP 同一规约）。 Verify with a real `invoke search_media` call returning live TMDB data, not just `hermes mcp test`. Requires `/reload-mcp` (or a new session) to appear in an active conversation.

First-run MP errors that are NORMAL config work (not 故障): `/Media/未整理` monitor dir missing, emby/transmission auth errors (zip carried foreign config), 站点 cookie 未设置.

## Jellyfin

### Finding Config Files
```bash
find /volume* -name 'system.xml' -path '*/jellyfin/*' 2>/dev/null
```

### Finding Port
Default: **8096**. Verify: `curl -s -o /dev/null -w '%{http_code}' http://NAS-IP:8096`

### Reading User Credentials
```bash
sqlite3 /path/to/jellyfin.db 'SELECT Username, Password, EnableAutoLogin FROM Users;'
```
Password is PBKDF2-SHA512 hash — cannot extract plaintext.

### Resetting Password
```python
import hashlib, base64, os, sqlite3

password = 'NEW_PASSWORD'
salt = os.urandom(16)
iterations = 210000
dk = hashlib.pbkdf2_hmac('sha512', password.encode(), salt, iterations)
salt_b64 = base64.b64encode(salt).decode().upper()
hash_b64 = base64.b64encode(dk).decode().upper()

# CRITICAL: use chr(36) for $, NOT literal $ in f-string
dollar = chr(36)
result = f'{dollar}PBKDF2-SHA512{dollar}iterations={iterations}{dollar}{salt_b64}{dollar}{hash_b64}'

db = sqlite3.connect('/path/to/jellyfin.db')
db.execute('UPDATE Users SET Password = ?, MustUpdatePassword = 0 WHERE Username = ?',
           (result, username))
db.commit()
db.close()
```

**Pitfall:** After updating hash, Jellyfin often needs restart. If web login still shows "连接失败":
```bash
sqlite3 /path/to/data/jellyfin.db 'UPDATE Users SET Password = NULL, MustUpdatePassword = 1 WHERE Username = "root";'
```
Then user logs in with no password and sets new one.

## Music Library Organization (Flat → Artist/Album/Track)

Media players expect `Artist/Album/Track` structure. If files are flat with complete metadata:
1. Check metadata: `ffprobe -v quiet -print_format json -show_format file.m4a`
2. Reorganize using Python script that reads tags via ffprobe
3. Rescan media library in Jellyfin/Emby/Plex

**Pitfalls:**
- Artist name inconsistencies (e.g. "G.E.M. 邓紫棋" vs "G.E.M.邓紫棋") cause split directories
- Track numbers like "13/144" suggest all songs from one playlist

## Sending Scripts to NAS When SCP Fails

```bash
cat /path/to/script.py | sshpass -p PASSWORD ssh -o StrictHostKeyChecking=no USER@IP "python3"
```
