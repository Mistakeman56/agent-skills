# 远程读屏 / 查窗口（Windows，从 Hermes 侧发命令）

用于「看一眼用户屏幕上到底怎么了」这类任务（游戏卡死、客户端弹窗、点击某个按钮）。
前置：用户 PC 上跑着 Windows-MCP HTTP 服务（console session），Hermes 侧有 `mcp__windows__*` 工具。

## session 0 vs console session（最容易误判的地方）

| 查询 | 走 ssh 的 PowerShell（session 0） | Windows-MCP 的 PowerShell（console session） |
|---|---|---|
| `Get-Process` / CPU / 内存 | 可以 | 可以 |
| `MainWindowHandle` / `MainWindowTitle` | 全 0 / 空 | 真实 |
| `GetForegroundWindow()` | 0 | 真实 HWND |
| `.Responding` | 恒 True（无意义） | 可信 |
| `IsHungAppWindow(hwnd)` | 拿不到 hwnd | 可用 |
| 枚举顶层窗口（EnumWindows） | 只看得到服务窗口站，几乎为空 | 完整 |

结论：**窗口状态一律在 session 3 查**，SSH 只用来读文件/日志/跑 bash。

```powershell
Add-Type @'
using System;using System.Runtime.InteropServices;
public class WX{
 [DllImport("user32.dll")] public static extern bool IsHungAppWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 public struct RECT{public int L,T,R,B;}
}
'@
$h = (Get-Process -Name 'League of Legends').MainWindowHandle
'hung=' + [WX]::IsHungAppWindow($h)
```

- `App` 工具的 `mode=switch,name=...` 只认已安装的应用，**不能按窗口标题切前台**；切前台用
  `ShowWindow(h,9)` + `SetForegroundWindow(h)`，然后回读 `GetForegroundWindow()` 确认真的切过去了。
- `Snapshot` 的 UI Tree **不包含 CEF/Electron 客户端内部元素**（LoL 客户端、微信等），只给窗口框；
  这类界面只能靠截图 + OCR 或直接点坐标。

## 截图与回传

在 console session 截图（`SystemInformation.VirtualScreen` 是 DPI-aware 的，同时给出负原点，双屏必须用它）：

```powershell
Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing
$vs=[System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp=New-Object System.Drawing.Bitmap($vs.Width,$vs.Height)
$g=[System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($vs.Left,$vs.Top,0,0,$bmp.Size)
$bmp.Save('C:\Users\Public\shot.png',[System.Drawing.Imaging.ImageFormat]::Png)
'ORIGIN=' + $vs.Left + ',' + $vs.Top + ' SIZE=' + $vs.Width + 'x' + $vs.Height
```

**回传不要用 scp**：Windows OpenSSH 的 scp 会把二进制截断在整 200KB 边界（实测 399354 → 204800 字节，
`file` 仍能认出 PNG，极具欺骗性）。用：

```bash
ssh user@192.0.2.10 'cat /c/Users/Public/shot.png' > /tmp/shot.png   # 不用 -t，二进制安全
ssh user@192.0.2.10 'md5sum /c/Users/Public/shot.png'; md5sum /tmp/shot.png   # 两端一致才算拿到
```

## 用 OCR 读屏上的字（不要用视觉模型描述整屏）

4K 双屏整屏截图丢给 vision_analyze 会被描述成完全无关的画面（实测把 Windows 桌面说成 Kali/HTB 桌面），
拿它读界面等于瞎猜。正确做法是本机 OCR + tsv 坐标：

```bash
apt-get install -y -qq tesseract-ocr tesseract-ocr-chi-sim    # 一次性
python3 - <<'EOF'
from PIL import Image
im = Image.open('/tmp/shot.png').convert('RGB')
# 窗口屏幕坐标 (x,y,w,h) → 图片坐标要减去 VirtualScreen 原点
im.crop((x-ox, y-oy, x-ox+w, y-oy+h)).resize((w*2, h*2), Image.LANCZOS).save('/tmp/win.png')
EOF
tesseract win.png out -l chi_sim+eng --psm 6 tsv
awk -F'\t' 'NR>1 && $12!="" && $11>50 {printf "x=%d y=%d conf=%.0f %s\n", $7,$8,$11,$12}' out.tsv
```

- 放大 2× 再 OCR 明显提高小字号识别率；`--psm 6` 适合整块界面，`--psm 11` 适合零散标签。
- tsv 的 x/y 是**裁剪图内**坐标，加上原点并除以放大倍数才是屏幕坐标，喂给 `Click(x,y)` 前换算回来。
- OCR 出现「上层窗口的文字」= 该窗口被别的窗口压住，说明你的前景切换没真生效——回去看 `GetForegroundWindow()`。
- `GetWindowRect` 给的是 DPI 虚拟化后的坐标（4K 150% 缩放下全屏窗口报 2560×1440），
  但截图是物理像素，两者混用会裁到别的窗口上。用 VirtualScreen 的比例换算，或先确认 PowerShell 进程的 DPI 感知。

## Git Bash 参数坑

- 斜杠开头的 Windows 参数会被 MSYS 当路径：`tasklist /fi "..."` 报 `无效参数 'C:/Program Files/Git/fi'`。
  写 `//fi`、`//fo`，或前缀 `MSYS_NO_PATHCONV=1`，或直接不用 tasklist 改走 PowerShell。
- 长脚本仍走 `ssh ... 'bash -s' < /tmp/x.sh`（stdin），或把 PowerShell 写在 heredoc 里落到
  `C:\Users\Public\x.ps1` 再 `-File` 执行，避免 `$`/引号被两层 shell 各吃一遒。
