# 对比基准：产物从哪拿 + 怎么测

用 Step 6 时的两条腿：**拿到可对比的官方产物**，**用 /proc 把数测出来**。
端点可能会变，每次现场验证，别把版本号/下载地址当真值写进记忆。

## 一、官方产物端点（无需注册、无需 API Key）

| 要什么 | 怎么拿 |
|---|---|
| **任意 JDK/JRE**（跑 JVM 系对照组最常缺的东西） | `https://api.adoptium.net/v3/binary/latest/<MAJOR>/ga/linux/x64/jre/hotspot/normal/eclipse` → 302 到 GitHub，`curl -L` 直接下 tar；查可用大版本用 `.../v3/info/release_names?architecture=x64&image_type=jre&os=linux&release_type=ga&version=[<M>,<M+1>)` |
| **Minecraft 原版服务端** | `https://piston-meta.mojang.com/mc/game/version_manifest_v2.json` → 找到版本 → 其 `url`（version json）→ `downloads.server.url`（piston-data，约 60 MB）；version json 里的 `javaVersion.major` 告诉你该配哪个 JDK |
| **Paper**（"当前主流实现"对照组） | `https://fill.papermc.io/v3/projects/paper` 列版本；`https://fill.papermc.io/v3/projects/paper/versions/<v>/builds/latest` → `downloads['server:default'].url` + `checksums.sha256` |
| **某生态的成熟度**（佐证"该不该追这个新版本"） | Modrinth：`https://api.modrinth.com/v2/search?query=&facets=[["versions:<V>"]]&limit=0` 看 `total_hits`；`/v2/project/<slug>` 看 `game_versions` / `loaders` 判断官方支持范围 |
| **release 资产 + 校验** | `https://api.github.com/repos/<o>/<r>/releases/tags/<tag>` → `assets[].url`、`body`（常含安装步骤与破坏性变更）；同 tag 下常有 `checksums.sha256` |

校验后再执行：`grep ' 文件名$' checksums.sha256 | sha256sum -c -`（文件名必须**锚到行尾**，
否则会匹配到同前缀的其他架构包）。

## 二、/proc 采样骨架（不装 psutil、不装 sysstat）

```python
import subprocess, time, os, signal, re

def read_vm(pid, key):                      # VmRSS / VmHWM / Threads
    for line in open(f'/proc/{pid}/status'):
        if line.startswith(key): return int(line.split()[1])

def cpu_ticks(pid):                          # utime+stime，单位 1/100s
    st = open(f'/proc/{pid}/stat').read().rsplit(')', 1)[1].split()
    return int(st[11]) + int(st[12])

def thread_names(pid):
    return sorted({open(f'/proc/{pid}/task/{t}/comm').read().strip()
                   for t in os.listdir(f'/proc/{pid}/task')})

p = subprocess.Popen(cmd, cwd=tmpdir, stdout=open('srv.log','w'), stderr=subprocess.STDOUT)
t0 = time.time(); ready = None
while time.time() - t0 < 180:                # 就绪 = 各产品自己的日志标志行
    time.sleep(0.2)
    if re.search(r'Done \(|Server is now running', open('srv.log').read()):
        ready = time.time() - t0; break
    if p.poll() is not None: break

time.sleep(20)                               # 静置后再读，避开启动脉冲
c1 = cpu_ticks(p.pid); time.sleep(10); c2 = cpu_ticks(p.pid)
cpu_pct = (c2 - c1) / (10 * os.sysconf('SC_CLK_TCK')) * 100
# 报：ready / VmRSS / VmHWM / Threads / cpu_pct / thread_names
p.send_signal(signal.SIGINT)                 # 优雅停，记 exit code
p.wait(timeout=60)
```

多核并行的测法不同：**对准负载那一段**（如世界生成）高频采 `/proc/stat` 各 `cpuN` 的非 idle 占比，
报 `峰值总占用%`（n 核上限 = n×100）与"忙过 >25% 的核数"，不要报空载平均。

## 三、读数时的三个坑

- 首跑 vs 热跑必须分开标；首跑含补丁/依赖/世界生成，量级不同。
- `-Xmx` 是分配上限不是占用；报 `VmRSS`。
- 单次样本只敢下"量级"结论；要"精度"就重复采样并给区间。
