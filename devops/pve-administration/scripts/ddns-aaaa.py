#!/usr/bin/env python3
"""把主域的 AAAA 记录刷成「本机当前的全局 IPv6」。

为什么需要：运营商家宽下发的 IPv6 是动态 PD 前缀，重拨后本机地址会变，
          AAAA 不跟着刷就变成指向死地址的断头路（浏览器优先 IPv6 → 整体打不开）。

用法：cron 每 10 分钟一次；或手动 python3 ddns-aaaa.py
依赖：同目录的 aliyun-dns.py（提供 api() 签名调用）
凭据：从 ~/.hermes/.aliyun.env 读 Ali_Key / Ali_Secret（变量名就是这个，
      不是 ACCESS_KEY_ID），永不打印到输出。
"""
import importlib.util, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ALIYUN_DNS = os.path.join(HERE, "aliyun-dns.py")
ALIYUN_DNS_FALLBACK = "~/.hermes/scripts/aliyun-dns.py"
DOMAIN = "example.com"


def load_aliyun():
    path = ALIYUN_DNS if os.path.exists(ALIYUN_DNS) else ALIYUN_DNS_FALLBACK
    spec = importlib.util.spec_from_file_location("ad", path)
    m = importlib.util.module_from_spec(spec)
    sys.modules["ad"] = m
    spec.loader.exec_module(m)
    return m


def get_my_ipv6():
    """取本机全局 IPv6（2408: 开头，EUI-64 格式；前缀变则地址变）"""
    try:
        out = subprocess.check_output(
            ["ip", "-6", "addr", "show", "scope", "global"], text=True, timeout=10)
    except Exception:
        return None
    for line in out.split("\n"):
        line = line.strip()
        if line.startswith("inet6 ") and "2408:" in line:
            addr = line.split()[1].split("/")[0]
            if not addr.startswith("fd"):
                return addr
    return None


def main():
    m = load_aliyun()
    my_v6 = get_my_ipv6()
    if not my_v6:
        print("未找到本机全局 IPv6")
        return 1

    r = m.api("DescribeDomainRecords", {"DomainName": DOMAIN, "PageSize": "100"})
    recs = r.get("DomainRecords", {}).get("Record", [])
    aaaa = [x for x in recs if x["RR"] == "@" and x["Type"] == "AAAA"]

    if not aaaa:
        out = m.api("AddDomainRecord", {"DomainName": DOMAIN, "RR": "@",
                                        "Type": "AAAA", "Value": my_v6, "TTL": "600"})
        print("已添加 AAAA %s (id=%s)" % (my_v6, out.get("RecordId")))
        return 0

    changed = 0
    for x in aaaa:
        if x["Value"] != my_v6:
            m.api("UpdateDomainRecord", {"RecordId": x["RecordId"], "RR": "@",
                                         "Type": "AAAA", "Value": my_v6, "TTL": "600"})
            print("已更新 AAAA: %s -> %s" % (x["Value"], my_v6))
            changed += 1
    if changed == 0:
        print("AAAA 已是最新: %s" % my_v6)
    return 0


if __name__ == "__main__":
    sys.exit(main())
