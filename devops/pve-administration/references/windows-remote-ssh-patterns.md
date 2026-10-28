# Windows Remote SSH Management Patterns

## Getting in: the user's username may not exist

Users give a username from memory and it is frequently wrong — their Windows login-screen name, an
old account, or a Microsoft-account alias, none of which is the SAM account name SSH authenticates
against. Guessing one name and reporting "认证失败" blames the wrong thing.

```bash
# 1. Try a short candidate list; print the RAW output, don't pattern-match it
for u in <PASSWORD> Administrator user; do
  echo "== $u ==" && timeout 20 sshpass -p "$PW" ssh \
    -o PreferredAuthentications=password -o PubkeyAuthentication=no \
    -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    -o LogLevel=ERROR "$u@$HOST" "hostname & whoami" 2>&1 | head -5
done

# 2. Then enumerate what actually exists
ssh ... "$OK_USER@$HOST" "net user"
```

- **Judge by the returned `whoami`, not by grepping for `denied`.** A `denied` match mislabels a
  connection that actually succeeded but printed nothing (empty `hostname`) — you then re-test
  credentials that already work and conclude the password is wrong.
- `net user` lists the SAM accounts; compare the user's stated name against it before suspecting the
  password. Console output is GBK so its headers come back mojibake, but the account names are ASCII
  and still readable — read the names, not the labels.

## PowerShell Variable Escaping Through SSH

When SSH into Windows, the SSH shell interprets `$` signs:
```bash
# BROKEN: $_ becomes /root._ on the Linux side
ssh user@win "powershell -Command \"Get-Process | Where ProcessName -like '*foo*'\""
```

**Workaround 1 — Write a .ps1 file first:**
```bash
ssh user@win "echo Get-Process ^| Where ProcessName -like '*foo*' > C:\\task.ps1 && powershell -ExecutionPolicy Bypass -File C:\\task.ps1"
```

**Workaround 2 — Use cmd.exe commands instead:**
```bash
ssh user@win "tasklist | findstr /i foo"
ssh user@win "dir /b C:\\path"
```

## Multi-line PowerShell: use `-EncodedCommand`, never inline

Anything longer than one line goes through base64 so no quoting survives to fight you:

```python
import subprocess as sp, base64
def ps(host, user, pw, script, timeout=180):
    b64 = base64.b64encode(script.encode("utf-16-le")).decode()   # PowerShell requires UTF-16LE
    r = sp.run(["sshpass", "-p", pw, "ssh", "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR",
                f"{user}@{host}",
                f"powershell -NoProfile -NonInteractive -EncodedCommand {b64}"],
               capture_output=True, timeout=timeout)
    # Windows console answers in GBK, not UTF-8
    return ((r.stdout or b"") + (r.stderr or b"")).decode("gbk", errors="replace").strip()
```

- **Encode as UTF-16LE**, not UTF-8 — PowerShell decodes `-EncodedCommand` as UTF-16 only; UTF-8 base64 fails silently or parses as garbage.
- **Decode output as `gbk`** with `errors="replace"` — a Chinese-locale Windows console emits GBK; UTF-8 decoding yields mojibake that hides the real error.
- Always pass `-NoProfile -NonInteractive` — profile scripts add startup latency and can prompt, which hangs a non-TTY SSH session.

## Scripts too long for the command line: local file → scp → run

A large base64 payload still hits the Windows command-line length ceiling (and SSH's own quoting). For anything substantial, never build the script as a remote string:

```python
pathlib.Path("/tmp/task.ps1").write_text(script, encoding="utf-8-sig")   # BOM so PowerShell reads UTF-8 correctly
sp.run(["sshpass", "-p", pw, "scp", "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null", "/tmp/task.ps1",
        f"{user}@{host}:D:/ComfyUI/_dl/task.ps1"], timeout=60)           # destination WITHOUT spaces
# then run it with a short command: powershell -NoProfile ... -File D:\path\task.ps1
```

- **scp destinations must not contain spaces** — quoting a spaced path (`"C:/Users/.../Start Menu/..."`) makes scp treat the whole quoted string as one literal filename and fail with `No such file or directory`. Upload to a space-free path, then copy into place with PowerShell (`Copy-Item` / `[Environment]::GetFolderPath('Startup')`).
- Write the local file with **`utf-8-sig`** — without the BOM, PowerShell 5.1 misreads the encoding of non-ASCII content and corrupts Chinese strings.
- Prefer PowerShell `@"..."@` here-strings **only after the script is already on disk**. Building a here-string inside a Python string that itself contains a here-string breaks in both directions — keep the two layers separate.
- **The length ceiling fails silently.** An over-long `-EncodedCommand` returns in well under a
  second with **exit code 0 and empty stdout** — no error anywhere, no non-zero status. Treat a
  suspiciously instant empty result as a payload-rejected signature, not as "the script printed
  nothing": shrink or split the payload instead of re-running it verbatim. (Observed at ~5.7 KB of
  encoded payload; stay comfortably under it and let scp carry anything bigger.)
- **Do not fall back to piping the script into `powershell -Command -`.** It parses the stream
  incrementally, so multi-line control flow (`if` / `else` / `foreach`) is cut at a chunk boundary
  and dies with a `ParserError` about an unexpected token — half the script runs and the other half
  never existed, which looks like the script "stopped partway" rather than like a transport bug.
  When one call is too long, split into several short single-purpose `-EncodedCommand` calls and
  chain their results; scp the file when the logic genuinely needs to be one script.
- **Non-ASCII in a piped script makes this failure masquerade as a Chinese-encoding bug.** The chunk
  boundary lands mid-multibyte character, so the `ParserError` quotes a garbled trailing token and
  the stdout simply stops after the last complete statement. Signals: the script dies exactly at a
  `foreach` / `if` block, or right after the first line carrying a non-ASCII literal. Read it as the
  stdin-chunking bug above — not as a locale problem to keep re-encoding.
- **When you must pipe, keep it to single-line one-liners and ASCII-only.** A `foreach ($x in $y) {
  ... }` written on one physical line survives; the same block split across lines does not. For
  registry/service writes prefer ASCII-only built-ins (`reg add`, `net`, `sc`) over
  `Set-ItemProperty`/`New-ItemProperty` — a cmdlet whose exception message is Chinese takes the
  session down with it and you lose everything already printed.
- **Route results through a file, read it in a second call.** Have the script
  `[IO.File]::AppendAllText('C:\dir\out.txt', $line, [Text.Encoding]::ASCII)` (or UTF-8) each step,
  then `type` that file from a *separate* SSH command. When stdout vanishes mid-run, the file's last
  line names the exact statement that died, and the file outlives the stdout channel.

## Processes launched over SSH die with the session

A child started by `Start-Process` under an SSH command is torn down when the connection closes, so a "started" service silently disappears the moment the script returns.

**For a bounded job** — schedule it detached:
```powershell
schtasks /Create /TN "MyJob" /TR "powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File D:\path\job.ps1" /SC ONCE /ST 23:59 /F
schtasks /Run /TN "MyJob"
```

**For a long-running service** — put a launcher in the Startup folder so it rides the user's login:
```vbs
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "D:\MyApp"
sh.Run "powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""D:\MyApp\start.ps1""", 0, False
```

- `schtasks /Create /RU <user> /RP <password>` **is rejected with "用户名或密码不正确"** for password-protected local accounts — the credential form is not accepted over SSH. Use the Startup folder instead of fighting the scheduler for a self-starting service.
- **For a detached daemon or monitor, `/RU SYSTEM /RL HIGHEST` needs no password** and runs in its
  own session: it survives SSH teardown *and* user logout, and `/SC ONSTART` turns it into a boot
  service. Prefer it over the Startup folder when the job is a background monitor rather than a
  per-login app.
- **Write the command to a `.bat` first, then point `/TR` at that file.** Nesting quotes inside
  `/TR "powershell ..."` fails from a `powershell -Command -` shell; `/TR 'C:\dir\run.bat'` (path
  only, quoted as a single token) succeeds.
- **Prove survival by a counter delta read from two separate SSH sessions** — sample a row count,
  wait *outside* the connection, then reconnect and sample again. Growth inside one connection proves
  nothing: a `Start-Process` child dies with the session and leaves the first few rows behind.
- The `0` in `sh.Run ..., 0, False` hides the console window; `False` returns immediately so the SSH call does not block on the service.
- Always verify a service actually came up with an HTTP/port probe (`Invoke-WebRequest ... /system_stats`), never by the fact that the launch command returned success.

## Verifying a process actually restarted

A kill filter that does not match leaves the old process alive, so a code patch appears not to work even though it landed on disk.

- **Match on the executable and relative script name** (`*main.py*`), never on a path fragment (`*ComfyUI\main.py*`). When the launcher uses `-WorkingDirectory` plus a relative argument, the process `CommandLine` contains only `main.py` — the directory part you are grepping for is not there, so the filter matches nothing and the kill is a no-op.
- **Cross-check `CreationDate` against the patch/write timestamp.** If the process started *before* the file changed, it is still running the old code regardless of what you "restarted". Reading the on-disk file proves the patch exists, not that anything loaded it.
- Restarting matters for more than servers: clear `__pycache__` when a `.pyc` may be stale, and confirm the port listener count drops to 0 before relaunching.

## A package manager's "success" text is not state — read the target back

`winget uninstall` printed `Successfully uninstalled` while **nothing actually changed**: the service
was still `Running`, the process still alive, 138 files still on disk, the registry uninstall entry
intact, and `winget list` still showing the old version. winget's silent mode never reaches an NSIS
installer's real uninstaller, so it reports success on a no-op.

**Procedure when upgrading a Windows app:**

1. **Record the pre-state first** so you can diff it: service status, process PID and `FileVersion`,
   install-dir file count, the registry uninstall entry (`DisplayName` + `DisplayVersion`), and
   `winget list --id <id>`.
2. Run the package manager's uninstall.
3. **Read every one of those back.** If any is still present it did not happen — do not install yet.
4. Fall back to the app's own uninstaller. Its path is the registry `UninstallString`, which you can
   read with `Get-ItemProperty` over the standard Uninstall keys and filter on `DisplayName`.
   NSIS uninstallers take `/S` for silent; run it with `Start-Process -PassThru -Wait` and check the exit code.
5. Read the state back **again** — service, process, files and registry all gone — then install the new version.
6. **Back up the config directory before step 2.** A native uninstaller happily takes the config with
   the program files; restore it afterwards (the usual survivors are the app config, `*.conf`, and
   any cert/key pairs).

**Why this matters:** reporting "uninstalled, now installing vNext" on top of a still-installed old
version makes the next step wrong in a way that is easy to miss — a side-by-side install, a stale
service still holding the port, the old `FileVersion` still running — and the user ends up being the
one who notices it.

## Chinese Filenames

```bash
ssh user@win "chcp 65001 >nul && dir C:\\Users\\user\\下载"
```

## Hermes sudo Limitation

`sudo -S` (password via stdin) is blocked by Hermes security policy. Workaround: give user local commands, or configure NOPASSWD sudo.

## wmic Deprecated

Use PowerShell alternatives:
```bash
ssh user@win "powershell -Command \"Get-PSDrive -PSProvider FileSystem\""
```

## GUI / tray apps cannot be started over SSH

`Start-Process` on a tray app (something whose job is to own a notification-area icon and then spawn
the real daemon) returns success and leaves **zero processes behind**: the session is non-interactive,
so it has no desktop to attach an icon to and the process exits at once.

**Rule: over SSH, launch the command-line daemon, not the GUI wrapper.** Look for a `serve` / `run` /
`--daemon` subcommand on the same binary (e.g. `ollama.exe serve` instead of `ollama app.exe`). If the
GUI wrapper is the only entry point, the service has to be started by a *logon* action — the Startup
folder shortcut — which means you cannot start it from SSH at all; either wait for the next login or
use the daemon form for the current session.

Always confirm with a count, not with the launch command's exit status:
```powershell
Get-Process -Name '<app>*' -EA SilentlyContinue | Measure-Object | Select-Object -Expand Count
```

## Launch the `.cmd` shim, not the `.ps1` shim

npm installs three shims for each global binary: `<name>` (extensionless), `<name>.cmd`, and
`<name>.ps1`. `Start-Process -FilePath '<name>'` resolves to the **`.ps1`** shim, which immediately
returns without running anything. Use `<name>.cmd` explicitly — it is the one that execs the real
binary (`node_modules\...\bin\<app>.exe`).

Two related rules for running a CLI agent over SSH:

- **Redirect stdin (`< NUL`)** or the tool blocks waiting for piped input and wastes a fixed delay
  (several seconds) before it gives up and proceeds.
- **Never wait synchronously for an agent's first response over SSH.** A heavy agent re-sends its full
  system prompt + tool schema every call, which can take minutes; the SSH timeout fires first and
  takes the output with it. Write a script that runs it with stdout/stderr redirected to files, launch
  it via `schtasks`, then **poll the output file** in later calls.

## `schtasks` discards stdout — pick the log channel before launching

A scheduled task throws away the job's stdout, so an application that logs *only* to stdout (the
classic daemon pattern) writes **nothing anywhere** once you start it that way — its usual log file
stays empty and the emptiness looks like "the app is broken".

Before launching under `schtasks`, decide how you will read the app's state afterwards:
- Point the script at its own log file explicitly (`... >> D:\app\app.log 2>&1`), **or**
- Drop the log entirely and plan to diagnose from independent probes instead: the app's own status
  command, `Get-NetTCPConnection -LocalPort <port>` for listeners, `nvidia-smi` for GPU work, and
  `Get-NetTCPConnection -OwningProcess` to see whether the client is actually connected.

An empty log is then *expected*, not a fault — do not spend calls chasing it.

## PowerShell 5.1 surface + CLIXML noise on stderr

- **No `??` / `?.` operators.** Windows PowerShell is 5.1; a null-coalescing operator is a **parse
  error that aborts the whole script**, so a one-line shortcut takes out the entire command. Use
  `if ($x) { ... } else { ... }` or `($x)` fallbacks.
- **`-f` format strings fail silently.** If any argument expression throws, the whole `Write-Output
  ('…{0}…' -f …)` line produces nothing — you get an empty result instead of an error. Print
  diagnostics with plain `+` concatenation when the value may be missing.
- **Filter CLIXML before parsing.** Progress records arrive on stderr wrapped in
  `#< CLIXML … </Objs>`; they are noise, not errors. Strip everything from `#< CLIXML` onward before
  comparing output, or a successful run will look like a failure.
- `2>$null` and `2>&1` swallow the message you actually need — when a remote call produces nothing,
  re-run once with stderr captured to a file before concluding anything.

## Verify a generated script before shipping it

A script whose paths or URLs were corrupted while being assembled fails **downstream** — the download
writes 0 bytes, the file "does not exist", the loop spins — and the symptom never mentions the path.

**Always assert the critical literals on the local copy before scp'ing:**
```python
assert "D:\\target_dir" in script        # expected absolute path is present
assert "171240" not in script             # a stray value from another computation is not
assert expected_filename in script
```

Variable-substitution bugs (a name bound to the wrong value, an f-string placeholder picking up a
leftover from an earlier cell) are the usual cause. The corrupted literal is nearly always a path or
a byte count — both worth checking by hand because both fail as "nothing happened" rather than as an
error.

## Reading device state: "no problems" does not mean "hardware is fine"

Three different commands answer three different questions, and the reassuring one is the least
useful. Collect all three before drawing a conclusion about a device that "disappeared":

```powershell
Get-PnpDevice -Class MEDIA,AudioEndpoint -EA SilentlyContinue |
  Select-Object Status, Class, Problem, FriendlyName, InstanceId | Format-Table -Auto

# per-device problem code (works even when Problem reads PHANTOM)
Get-PnpDeviceProperty -InstanceId $id -KeyName 'DEVPKEY_Device_ProblemCode' -EA SilentlyContinue

pnputil /enum-devices /problem     # ← excludes phantom devices; "No devices" is NOT a clean bill
```

| Readout | Meaning | Action |
|---|---|---|
| `Problem = CM_PROB_NONE`, `Status = OK` | enumerated and healthy | look elsewhere |
| `Problem = CM_PROB_PHANTOM`, `Status = Unknown` | **registry record kept, hardware not present on the bus** — the device did not answer enumeration | hardware/power/firmware level, not a driver fault |
| `Problem = <code>` with `Status = Error` | enumerated but failing (Code 10/28/52 …) | driver/reinstall path |
| `ConfigFlags = 0` | **not** disabled by policy | don't waste a call "enabling" it |
| `pnputil /problem` → `No devices were found` | only proves no *enumerated* device has a code | phantoms are invisible to it — pair it with `Get-PnpDevice` |

Endpoint state comes from the registry under
`HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\{Render,Capture}\*\DeviceState`:
`1` ACTIVE · `2` DISABLED · `4` NOTPRESENT · `8` UNPLUGGED. A pile of `4` with healthy services is
the classic signature of "driver present, hardware absent" — which is a hardware finding, not a
software one.

**Software volume/mute is a *localizer*, not a fix.** `waveOutSetVolume` counts **16 bits per channel**
against 65535 — compute the hex, never eyeball it (`0x1333` = 7.5%, not 30%; 30% ≈ `0x4CCC`, 40% ≈
`0x6666`, each channel duplicated into the high word: `lo | (hi << 16)`), then read it back with
`waveOutGetVolume` before trusting it. Use volume = 0 / mute / endpoint-disable as a **probe**: a fault
that does *not* respond to any of them is generated downstream of the DAC (amplifier, ground, inductor,
MLCC whine) — software is exonerated, so stop restarting services and escalate to power/ground/hardware.
Silence that *does* follow an endpoint disable means the amplifier was being held enabled — that is the
one software-side signature worth acting on.

**Acoustic noise that tracks CPU power state** (louder on battery or under load transitions, gone when
the machine sleeps, and ignoring the volume slider) is inductor/MLCC whine from DVFS/C-state, not a dead
codec. Remedy in order: `powercfg /setacvalueindex SCHEME_CURRENT SUB_PROCESSOR PROCTHROTTLEMIN 5` plus
`/setdcvalueindex … 5` plus `/setactive SCHEME_CURRENT` (the stock balanced plan often ships a high AC
minimum — 80% observed on one laptop), then disable C-state / CPU Power Management in BIOS for the
durable fix, at the cost of battery life and fan speed. Re-read the state table afterwards; if the codec
still reads `CM_PROB_PHANTOM`, the power/amplifier circuit is implicated — fix power state first and
re-read before touching drivers.

**⚠️ Do not `pnputil /scan-devices` on a machine presenting as a hardware fault.** A rescan forces
re-enumeration; on a device that is marginal (failing codec, over-current protection, bad
filter caps) it can re-assert power/enable to the faulty circuit and **make the symptom worse** —
a silent device came back audibly loud. Rescan is a *software* remedy: use it only after the state
table above says the device is enumerated-but-failing, never as a first probe of an absent device.

**Triage order for "the device is gone":**
1. Read state (table above) — distinguish *absent* from *failing*.
2. For *absent*: check whether sibling devices on the same bus are still OK. If they are, the bus is
   alive and only that endpoint dropped → power/protection/BIOS level.
3. Stop and escalate to the user (power-cycle, grounded outlet, service) — do not rescan, do not
   reinstall drivers, don't restart services hoping to conjure hardware back.
4. Rescan / service restart only once the state says *enumerated-but-failing*.

For "the machine made a loud noise and then the device vanished", the sound is evidence: an audible
fault (oscillation, over-current, floating ground) plus a later phantom state points at the power or
amplifier circuit. Report the physical symptom alongside the software state — neither alone is the
answer.
