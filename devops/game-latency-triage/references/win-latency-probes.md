# PC 侧延迟取证（Windows / Git Bash over SSH）

只读命令，不会改任何设置。用于把「网络层」彻底洗清，或排查显卡/显示器/串流侧的输入链路。

## 1. 高密度 RTT + 抖动（首选，20 秒出结果）

`Test-Connection -Delay` 最小只接受 1（`-Delay 0` 会参数校验报错），要 0.15s 级采样用 .NET 原生 Ping：

```powershell
$p = New-Object System.Net.NetworkInformation.Ping
foreach ($ip in @('203.0.113.1','203.0.113.1','192.0.2.10')) {
  $ts = @(); $lost = 0
  for ($i=0; $i -lt 60; $i++) {
    try { $r = $p.Send($ip, 1000); if ($r.Status -eq 'Success') { $ts += $r.RoundtripTime } else { $lost++ } } catch { $lost++ }
    Start-Sleep -Milliseconds 150
  }
  if ($ts.Count -gt 0) {
    $avg = ($ts | Measure-Object -Average).Average; $max = ($ts | Measure-Object -Maximum).Maximum; $min = ($ts | Measure-Object -Minimum).Minimum
    $j = 0.0; $n = 0; for ($k=1; $k -lt $ts.Count; $k++) { $j += [math]::Abs($ts[$k] - $ts[$k-1]); $n++ }
    $jit = if ($n -gt 0) { $j/$n } else { 0 }
    Write-Output ('{0,-16} 收到={1}/60 丢={2} 最小={3}ms 平均={4:N1}ms 最大={5}ms 抖动={6:N2}ms' -f $ip, $ts.Count, $lost, $min, $avg, $max, $jit)
  } else { Write-Output ('{0,-16} 全部超时' -f $ip) }
}
```

调用方式（沿用 pc-remote-ops：ssh + `bash -s` stdin，末尾 `2>&1 | iconv -f GBK -t UTF-8` 防乱码）。
实测参考值：PC→网关 0ms、PC→国服游戏服 14~15ms 抖动 0.24ms、0 丢包 = 网络层没有问题。

不要用 `ping -n 200 -w 100` 做这件事：经 ssh + iconv 管道经常整条命令挂到 300s 超时，白等。

## 2. 找到"正在跟谁通信"

路由器上锚定原始方向取字段（回程元组里也有 dst=，取错就 ping 到本机公网 IP）：

```sh
awk '/udp/ && ($6=="src=192.0.2.10") {print $7, $9}' /proc/net/nf_conntrack | sort | uniq -c | sort -rn | head
```

字段位置随行首前缀变化，稳妥写法是只取每行第一次出现的 `src=<LAN_IP>` 之后的 `dst`/`dport`。
8000/8081 多是平台/语音心跳，对局服的包率更高（20~30 pps），按 `packets=` 排序就能认出来。

## 3. 显示/合成/串流体检（网络洗清后看这里）

```powershell
# 显示器与刷新率、是否挂了虚拟显示器
Get-CimInstance Win32_VideoController | Select-Object Name,CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate,DriverVersion | Format-List
# 串流类常驻进程（GameViewer=向日葵、ToDesk、Parsec、Moonlight、nvstreamer）
Get-Process | Where-Object {$_.ProcessName -match 'GameViewer|Sunlogin|ToDesk|Parsec|Moonlight|nvstreamer|Oray'} | Select-Object ProcessName,Id,CPU | Format-Table -AutoSize
# 是否有活跃串流会话（只有一条到厂商 443 的信令连接 = 没人在串流，但虚拟显示器仍挂着）
$pids = (Get-Process GameViewer* -ErrorAction SilentlyContinue).Id
Get-NetTCPConnection -ErrorAction SilentlyContinue | Where-Object {$_.OwningProcess -in $pids -and $_.State -eq 'Established'} | Select-Object LocalPort,RemoteAddress,RemotePort
# GPU 是否降频（pstate 应为 P0/P2，LOL 这类轻载 20~30% util 属正常）
nvidia-smi --query-gpu=utilization.gpu,memory.used,temperature.gpu,clocks.gr,power.draw,pstate --format=csv,noheader
```

判读：
- 多出来的 `3840x2160@159` 之类适配器 = 虚拟显示器，合成器多绕一层，做 A/B 时优先退掉。
- 鼠标：`Get-PnpDevice` 里同时出现多个 2.4G 接收器（ROG OMNI RECEIVER、雷蛇 dongle）时，
  问一句是否开了 8000Hz 轮询——6 核 CPU 上会额外抢输入线程，手感反而不稳。
- 游戏内垂直同步 / 帧率上限 / NVIDIA Reflex 远程读不到，直接让用户看一眼，别硬查注册表。
