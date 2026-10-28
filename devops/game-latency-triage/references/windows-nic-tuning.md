# Windows 游戏 PC 网卡/显示链路体检（只读优先）

全部经 SSH 进 Windows（`ssh user@ip 'bash -s' <<'EOF'`）后调 `powershell.exe -NoProfile -Command "..."`，
输出管道接 `| iconv -f GBK -t UTF-8 2>/dev/null`（中文 Windows 默认 GBK）。

## 体检（只读，先跑这组）

```powershell
Get-NetAdapter | Where-Object Status -eq 'Up' | Select-Object Name,InterfaceDescription,MacAddress,LinkSpeed | Format-List
Get-NetAdapterAdvancedProperty -Name '以太网' | Select-Object DisplayName,RegistryKeyword,DisplayValue | Format-Table -AutoSize
```

关注四项节能（默认多数是「开启」，对延迟不利）：
`*EEE`、`EnableGreenEthernet`、`GigaLite`、`*InterruptModeration`。

顺带看：`*SpeedDuplex`（应为自动侦测且协商到 2.5G/1G）、`*PowerSavingMode`、
`*ReceiveBuffers`/`*TransmitBuffers`（1024/512 够用）、`*FlowControl`。

显示/串流侧：

```powershell
Get-CimInstance Win32_VideoController | Select-Object Name,CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate,DriverVersion | Format-List
powercfg /getactivescheme
Get-Process | Where-Object {$_.ProcessName -match 'GameViewer|Sunlogin|ToDesk|Parsec|Moonlight'} | Select-Object ProcessName,Id,CPU | Format-Table -AutoSize
Get-Service | Where-Object {$_.Name -match 'GameViewer|Sunlogin'} | Select-Object Name,Status,StartType | Format-Table -AutoSize
```

`Win32_VideoController` 里除独显外多出来的那一行（例：`GameViewer Virtual Display Adapter`）
就是串流软件的虚拟显示器——它常驻即意味着合成器多一层，是「ping 正常但不跟手」的常见嫌疑。
判断是否真的有人在串流：`Get-NetTCPConnection | Where-Object {$_.OwningProcess -in <串流进程PID> -and $_.State -eq 'Established'}`，
只有一条到厂商 443 的信令连接 = 空闲，但虚拟显示器仍在。

## 改节能四项（需管理员，会断网约 10s）

先备份，改前基线可回滚：

```powershell
Get-NetAdapterAdvancedProperty -Name '以太网' | Select-Object DisplayName,RegistryKeyword,DisplayValue,RegistryValue |
  Export-Csv -Path C:\Users\<user>\nic_backup_$(Get-Date -Format yyyyMMdd_HHmmss).csv -NoTypeInformation -Encoding UTF8
```

再改 + 重启网卡 + 读回验证：

```powershell
$n='以太网'
foreach ($kv in @(@('*EEE',0),@('EnableGreenEthernet',0),@('GigaLite',0),@('*InterruptModeration',0))) {
  try { Set-NetAdapterAdvancedProperty -Name $n -RegistryKeyword $kv[0] -RegistryValue $kv[1] -NoRestart -ErrorAction Stop
        "OK  $($kv[0]) -> $($kv[1])" }
  catch { "FAIL $($kv[0]): $($_.Exception.Message)" }
}
Restart-NetAdapter -Name $n -Confirm:$false
Start-Sleep -Seconds 4
Get-NetAdapterAdvancedProperty -Name $n |
  Where-Object {$_.RegistryKeyword -in '*EEE','EnableGreenEthernet','GigaLite','*InterruptModeration'} |
  Select-Object RegistryKeyword,DisplayName,DisplayValue | Format-Table -AutoSize
```

回滚：按备份 CSV 里 `RegistryKeyword`/`RegistryValue` 逐项 `Set-NetAdapterAdvancedProperty -RegistryValue <旧值>`，
再 `Restart-NetAdapter`。

## 注意

- 需要管理员会话（`net session >/dev/null 2>&1 && echo ADMIN=YES`）才能改；只读查询不需要。
- `Restart-NetAdapter` 会把当前 SSH 连接断掉，命令本身可能报错返回——改完**必须另起一次 SSH 读回**确认，
  不要以「命令报错」判定失败。
- `Get-NetAdapterStatistics` 在部分 Realtek 驱动上 `ReceivedPackets` 等字段为空，只用 `ReceivedBytes` 和
  `ReceivedPacketErrors` 做基线即可。
