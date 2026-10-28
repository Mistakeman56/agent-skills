#!/usr/bin/env python3
"""APK 体检：判断为什么安卓安装时提示"解析失败"。
不需要 aapt/androguard：zipfile + 自写二进制 AXML 解析 + APK Signing Block 检测。

用法: python3 apk_probe.py /path/to/xxx.apk[.1]

输出：文件头/完整性、ABI、v1/v2/v3 签名、package/minSdk/targetSdk/权限、启动 Activity。
配套阅读 SKILL.md 的「Diagnosing 解析失败」一节，按那里的顺序判因。
"""
import hashlib
import os
import struct
import sys
import zipfile

RES_STRING_POOL = 0x0001
RES_XML_START_ELEMENT = 0x0102
RES_XML_END_ELEMENT = 0x0103
TYPE_INT_DEC = 0x10
TYPE_INT_HEX = 0x11
TYPE_STRING = 0x03
TYPE_INT_BOOLEAN = 0x12


def read_string_pool(buf, off):
    """返回 (strings, next_offset)"""
    typ, hsize, size = struct.unpack_from("<HHI", buf, off)
    string_count, style_count, flags, strings_start, styles_start = struct.unpack_from("<IIIII", buf, off + 8)
    utf8 = bool(flags & (1 << 8))
    offsets = struct.unpack_from(f"<{string_count}I", buf, off + hsize)
    base = off + strings_start
    out = []
    for o in offsets:
        p = base + o
        if utf8:
            n = buf[p]
            p += 2 if n & 0x80 else 1
            n2 = buf[p]
            if n2 & 0x80:
                n2 = ((n2 & 0x7F) << 8) | buf[p + 1]
                p += 2
            else:
                p += 1
            out.append(buf[p:p + n2].decode("utf-8", "replace"))
        else:
            n = struct.unpack_from("<H", buf, p)[0]
            p += 2
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", buf, p)[0]
                p += 2
            out.append(buf[p:p + n * 2].decode("utf-16-le", "replace"))
    return out, off + size


def parse_axml(data):
    """解析二进制 AndroidManifest.xml，返回 (strings, elements[])"""
    strings = []
    elements = []
    off = 8  # skip RES_XML header
    total = struct.unpack_from("<I", data, 4)[0]
    while off < total and off + 8 <= len(data):
        typ, hsize, size = struct.unpack_from("<HHI", data, off)
        if size == 0:
            break
        if typ == RES_STRING_POOL:
            strings, _ = read_string_pool(data, off)
        elif typ == RES_XML_START_ELEMENT:
            ns, name = struct.unpack_from("<iI", data, off + 16)
            attr_start, attr_size, attr_count = struct.unpack_from("<HHH", data, off + 24)
            attrs = []
            ap = off + 16 + attr_start
            for _ in range(attr_count):
                a_ns, a_name, a_raw = struct.unpack_from("<iii", data, ap)
                t_size, t_res0, t_type = struct.unpack_from("<HBB", data, ap + 12)
                t_data = struct.unpack_from("<I", data, ap + 16)[0]
                nm = strings[a_name] if 0 <= a_name < len(strings) else f"?{a_name}"
                if t_type == TYPE_STRING and t_data < len(strings):
                    val = strings[t_data]
                elif t_type in (TYPE_INT_DEC, TYPE_INT_HEX):
                    val = str(t_data)
                elif t_type == TYPE_INT_BOOLEAN:
                    val = "true" if t_data else "false"
                else:
                    val = f"0x{t_data:x}"
                attrs.append((nm, val))
                ap += attr_size
            elements.append((strings[name] if 0 <= name < len(strings) else "?", attrs))
        off += size
    return strings, elements


def apk_signing_block(path):
    """检测 APK Signing Block 及其签名方案版本。返回 (v2, v3, v31, note)"""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        fsize = f.tell()
        tail = min(fsize, 66000)
        f.seek(fsize - tail)
        buf = f.read()
    i = buf.rfind(b"PK\x05\x06")
    if i < 0:
        return False, False, False, "找不到 EOCD（不是完整 ZIP）"
    cd_off = struct.unpack_from("<I", buf, i + 16)[0]
    if cd_off < 24:
        return False, False, False, "no signing block"
    with open(path, "rb") as f:
        f.seek(cd_off - 24)
        foot = f.read(24)
        magic = foot[8:24]
        if magic != b"APK Sig Block 42":
            return False, False, False, "无 APK Signing Block（仅 v1 签名或未签名）"
        size = struct.unpack_from("<Q", foot, 0)[0]
        start = cd_off - 8 - size
        f.seek(start)
        blk = f.read(size)
    has2 = has3 = has31 = False
    p = 8
    while p + 12 <= len(blk):
        plen = struct.unpack_from("<Q", blk, p)[0]
        if plen <= 4:
            break
        pid = struct.unpack_from("<I", blk, p + 8)[0]
        if pid == 0x7109871A:
            has2 = True
        elif pid == 0xF05368C0:
            has3 = True
        elif pid == 0x1B93AD61:
            has31 = True
        p += 8 + plen
    return has2, has3, has31, "ok"


def main(path):
    print("=" * 62)
    print("APK 体检报告")
    print("=" * 62)
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(8)
    md5 = hashlib.md5(open(path, "rb").read()).hexdigest()
    print(f"文件: {os.path.basename(path)}")
    print(f"大小: {size:,} 字节 ({size/1024/1024:.2f} MB)")
    print(f"MD5 : {md5}")
    print(f"文件头: {head[:4]!r}  → {'✓ ZIP/APK 格式' if head[:2] == b'PK' else '✗ 不是 ZIP/APK（下载损坏或格式不对）'}")

    print("\n[1] 压缩包完整性")
    meta = []
    try:
        z = zipfile.ZipFile(path)
        bad = z.testzip()
        names = z.namelist()
        print(f"  条目数: {len(names)}")
        print(f"  完整性: {'✓ 通过' if bad is None else f'✗ 损坏文件: {bad}'}")
        for n in ("AndroidManifest.xml", "classes.dex", "resources.arsc"):
            print(f"  {n}: {'✓' if n in names else '✗ 缺失'}")
        dexs = [n for n in names if n.startswith("classes") and n.endswith(".dex")]
        print(f"  dex 文件: {dexs}")
        if "classes.dex" in names:
            with z.open("classes.dex") as d:
                magic = d.read(8)
            print(f"  dex 版本: {magic[:7].decode('ascii', 'replace')} (035=Android5以下/039=Android9+)")
        libs = [n for n in names if n.startswith("lib/")]
        abis = sorted({n.split("/")[1] for n in libs if len(n.split("/")) > 1})
        print(f"  native 库架构: {abis if abis else '无 (纯 Java/WebView)'}")
        print(f"  native 库数量: {len(libs)}")
        meta = [n for n in names if n.upper().startswith("META-INF/") and
                n.upper().endswith((".RSA", ".DSA", ".EC", ".SF"))]
        print(f"  META-INF 签名文件: {meta if meta else '无（无 v1 签名）'}")
        joined = " ".join(names)
        if "assets/apps" in joined or any("__UNI__" in n for n in names):
            print("  框架: UniApp (DCloud)")
        elif any(n.startswith("assets/www/") for n in names):
            print("  框架: Cordova/Capacitor (WebView)")
        if any(n.endswith((".apk", ".apks")) for n in names):
            print(f"  注意: 包内还有 apk: {[n for n in names if n.endswith(('.apk','.apks'))][:5]}")
        print(f"  zip64: {'是' if any(i.file_size > 0xFFFFFFFF for i in z.infolist()) else '否'}")
    except Exception as e:
        print(f"  ✗ 打不开: {e}")
        return

    print("\n[2] 签名方案")
    v1 = bool(meta)
    v2, v3, v31, note = apk_signing_block(path)
    print(f"  v1 (jar 签名) : {'✓' if v1 else '✗'}")
    print(f"  v2 (APK Signing Block) : {'✓' if v2 else '✗'}")
    print(f"  v3 : {'✓' if v3 else '✗'}   v3.1: {'✓' if v31 else '✗'}")
    print(f"  说明: {note}")
    print("  判定: Android 11+ 要求至少 v2 签名 —— 只有 v1 的包在 Android 11 及以上会【解析失败】")

    print("\n[3] AndroidManifest 关键信息")
    try:
        data = zipfile.ZipFile(path).read("AndroidManifest.xml")
        strings, elements = parse_axml(data)
        for name, attrs in elements:
            if name == "manifest":
                for k, v in attrs:
                    if k in ("package", "versionCode", "versionName", "compileSdkVersion",
                             "platformBuildVersionCode", "platformBuildVersionName"):
                        print(f"  {k} = {v}")
            if name == "uses-sdk":
                for k, v in attrs:
                    print(f"  {k} = {v}")
            if name == "uses-permission":
                for k, v in attrs:
                    if k == "name":
                        print(f"  权限: {v}")
        for name, attrs in elements:
            if name == "activity" and any(v.endswith("LAUNCHER") for k, v in attrs):
                for k, v in attrs:
                    if k == "name":
                        print(f"  启动 Activity: {v}")
    except Exception as e:
        print(f"  ✗ 解析失败: {e}")

    print("\n[4] 判因提示")
    print("  minSdkVersion 换算成 Android 版本：28=9.0, 29=10, 30=11, 31=12, 33=13, 34=14, 35=15, 36=16")
    print("  设备系统 < minSdk → INSTALL_FAILED_OLDER_SDK；只有 arm64-v8a 库 + 32 位 ROM/x86 模拟器 → NO_MATCHING_ABIS")
    print("  文件名被改（微信 .apk.1）→ 先改名重试，这是最便宜的修复")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
