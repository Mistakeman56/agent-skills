---
name: apk-analysis
description: "Analyze Android APK files — extract metadata, check architecture compatibility, parse UniApp/web-app manifests, verify device compatibility. No aapt needed."
tags: [android, apk, mobile, compatibility]
---

# APK Analysis

## Trigger Conditions

- User sends an `.apk` file and asks about compatibility, what it does, or whether it can run on a device
- User asks "这个APP能装在我的手机上吗" or similar
- Need to inspect an APK's contents without aapt/android SDK

## Technique: Python zipfile + manifest parsing

APK files are ZIP archives. No `aapt` or Android SDK required.

### Step 1: Identify the APK

```python
import zipfile, json, re

with zipfile.ZipFile('/path/to/file.apk', 'r') as z:
    files = z.namelist()
    print(f"File count: {len(files)}")

    # Check for UniApp / web-based frameworks
    if any('manifest.json' in f and '__UNI__' in f for f in files):
        print("Framework: UniApp (DCloud)")
    elif 'assets/www/' in ' '.join(files):
        print("Framework: Cordova/Capacitor (web-based)")
    else:
        print("Framework: Native Android")
```

### Step 2: Extract app metadata

```python
with zipfile.ZipFile('/path/to/file.apk', 'r') as z:
    # UniApp: read manifest.json
    for name in z.namelist():
        if name.endswith('manifest.json') and '__UNI__' in name:
            manifest = json.loads(z.read(name))
            print(f"Name: {manifest.get('name')}")
            print(f"Version: {manifest.get('version', {}).get('name')}")
            print(f"Version code: {manifest.get('version', {}).get('code')}")
            print(f"Permissions: {list(manifest.get('permissions', {}).keys())}")
            # Tab bar pages reveal app structure
            tabs = manifest.get('plus', {}).get('tabBar', {}).get('list', [])
            print(f"Tabs: {[t.get('text') for t in tabs]}")
            break

    # Check gradle.properties for build info
    for name in z.namelist():
        if name.endswith('gradle.properties'):
            print(z.read(name).decode('utf-8', errors='replace'))
            break
```

### Step 3: Check architecture compatibility

**Critical check:** What native libraries (.so files) does the APK include?

```python
with zipfile.ZipFile('/path/to/file.apk', 'r') as z:
    libs = [f for f in z.namelist() if f.startswith('lib/')]
    architectures = set()
    for lib in libs:
        # lib/arm64-v8a/libfoo.so → arm64-v8a
        parts = lib.split('/')
        if len(parts) >= 2:
            architectures.add(parts[1])

    print(f"Architectures: {architectures}")

    # Common arch meanings:
    # armeabi-v7a = 32-bit ARM (old phones)
    # arm64-v8a   = 64-bit ARM (modern phones, 2016+)
    # x86         = 32-bit Intel (emulators, rare)
    # x86_64      = 64-bit Intel (emulators, rare)
```

**Compatibility matrix:**

| APK has | Device arch | Compatible? |
|---------|-------------|-------------|
| arm64-v8a only | arm64-v8a | ✅ |
| arm64-v8a only | armeabi-v7a (32-bit only) | ❌ |
| armeabi-v7a only | arm64-v8a | ✅ (runs in 32-bit compat mode) |
| armeabi-v7a + arm64-v8a | either | ✅ |
| no libs (pure web/app) | any | ✅ |

### Step 4: Identify framework-specific details

**UniApp indicators:**
- `assets/apps/__UNI__XXXXX/` directory
- `lib/arm64-v8a/libweex*.so` (Weex renderer)
- `lib/arm64-v8a/libuts-runtime.so` (UniApp TypeScript runtime)
- `assets/apps/__UNI__XXXXX/www/manifest.json` → app config

**Cordova/Capacitor indicators:**
- `assets/www/` directory
- `assets/cordova.js` or `assets/capacitor.js`

**Native indicators:**
- `classes.dex` directly in root (no www/ or __UNI__ assets)
- Large `.so` files (>10MB each = heavy native code)

### Step 5: Compatibility verdict template

```
APP: [name] v[version]
Framework: [UniApp/Cordova/Native]
Size: [file size]

Architecture: [arm64-v8a only / armeabi-v7a+arm64-v8a / etc.]
Target device: [device name] ([chip], [arch])
Compatibility: ✅ Compatible / ❌ Incompatible

[If incompatible: explain why and suggest alternatives]
```

## Diagnosing 「解析失败」(parse error) at install time

Work this order — it usually nails the cause in one pass:

1. **Does the phone's Android version meet `minSdkVersion`?** #1 cause; error code `INSTALL_FAILED_OLDER_SDK`.
   API = android version + 21 (9=28, 10=29, 11=30, 12=31, 13=33, 14=34, 15=35, 16=36).
   Real case: an APK with `minSdkVersion=28` failed on a 荣耀8C running Android 8.1 (API 27) — other APKs
   installed fine because they required less. "Other apps install fine but this one won't" points here.
2. **Filename mangling** — WeChat/QQ save received APKs as `.apk.1` (then `.apk.1(1).1`); some ROMs refuse to
   parse that. Cheapest fix, rule it out first: rename to `.apk` and retry.
3. **ABI** — `lib/` with **only** `arm64-v8a` cannot run on a 32-bit ROM, and x86 emulators (雷电/MuMu) fail with
   `INSTALL_FAILED_NO_MATCHING_ABIS`. Never suggest an x86 emulator for an arm64-only APK.
4. **Signature scheme** — `META-INF/*.RSA` = v1; an `APK Sig Block 42` footer just before the central directory
   carries v2 (`0x7109871a`) / v3 (`0xf05368c0`). Android 11+ rejects v1-only APKs.
5. **Format/integrity** — magic must be `PK\x03\x04`, `unzip -t` must pass, `AndroidManifest.xml` + `classes.dex` must exist.

`aapt`/`apktool`/`androguard` are usually absent; a ~150-line Python AXML parser (string pool + START_ELEMENT
attribute typed values) reads `package`, `minSdkVersion`, `targetSdkVersion` and permissions fine —
a working probe ships with this skill at `scripts/apk_probe.py`
(run `python3 scripts/apk_probe.py /path/to/file.apk` — one shot reports magic/integrity, ABI list, v1/v2/v3
signatures, package/versionName, `minSdkVersion`/`targetSdkVersion` and permissions). `java`/`keytool`/`7z` are normally available.

### Sideloading blocks by vendor (give the exact toggle path)

- **华为/荣耀 HarmonyOS 3.1+/4+**: 纯净模式 can no longer be fully disabled — instead 设置→系统和更新→纯净模式→
  **关闭「增强防护」**, plus 设置→安全→更多安全设置→**安装外部来源应用→文件管理→打开**. HarmonyOS ≤3.0 can exit
  纯净模式 outright. **HarmonyOS NEXT (5.0, 纯血鸿蒙) cannot install APKs at all.**
- **小米 HyperOS**: 设置→应用设置→授权管理→安装未知应用→允许; dismiss the red risk prompt with 继续安装.

## Pitfalls

- **`aapt` is rarely installed** — use zipfile + manifest.json parsing instead. No Android SDK needed.
- **UniApp apps are WebView-based** — they're lightweight and run on almost any modern Android device. Architecture compatibility is the main concern.
- **APK filenames are often mangled** by messaging platforms (WeChat adds `doc_xxx_` prefix, file extension may be duplicated like `.apk.1.1.1`). Check actual file type with `file` command. Always tell the user to rename it back to `.apk` before installing — this alone fixes many "解析失败" reports, and a cache copy can be re-sent with a clean name.
- **Some APKs have multiple DEX files** (`classes.dex`, `classes2.dex`, etc.) — this is normal for large apps ( multidex).
- **Permissions in manifest reveal app capabilities** — Camera, OAuth, Payment suggest a full-featured app. Only Internet permission suggests a simple web wrapper.
