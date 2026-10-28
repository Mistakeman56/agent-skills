#!/usr/bin/env python3
"""自建服务的 SQLite / 文件数据备份（通过 PVE pct exec 远程拉取）。

适用：数据存 SQLite 的 Docker 服务（Vaultwarden、各类面板等），
数据目录挂在 LXC 内的 /opt/<service>/data。

设计要点（都是踩过的坑）：
  * WAL 模式必须连 -wal / -shm 一起拿，只拷主库会丢最近写入
  * 容器里通常没有 sqlite3 命令，别指望 .backup，直接 cat
  * make_archive 格式名是 'gztar'，写 'gzip' 会抛 ValueError
  * 备份后解包验真（pragma integrity_check + 数表），不只看大小

用法：改下面 CONFIG 的常量，或 python3 本脚本 <ctid> <远程数据目录> <服务名>
"""
import os
import sys
import shutil
import sqlite3
import subprocess
import datetime

# ---- CONFIG（按服务改这里）----
PVE = "192.0.2.10"
CTID = "321"
REMOTE_DATA = "/opt/vaultwarden/data"
SERVICE = "vaultwarden"
EXTRA_FILES = ["rsa_key.pem", "rsa_key.pub.pem", "config.json"]
BACKUP_DIR = "~/.hermes/backups/vaultwarden"
KEEP = 30
# --------------------------------

DB_FILES = ["db.sqlite3", "db.sqlite3-wal", "db.sqlite3-shm"]
ENV_FILE = "~/.hermes/.env"


def pve_password():
    with open(ENV_FILE, encoding="utf-8") as f:
        for line in f:
            if line.startswith("PVE_ROOT_PASSWORD="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("PVE_ROOT_PASSWORD not found in " + ENV_FILE)


def pull(password, remote_path, local_path):
    """pct exec ... cat 远程文件 → 本地。文件不存在返回 False。"""
    cmd = (
        f"sshpass -e ssh -o StrictHostKeyChecking=no root@{PVE} "
        f"'pct exec {CTID} -- cat {remote_path}'"
    )
    r = subprocess.run(cmd, shell=True, capture_output=True,
                       env=dict(os.environ, SSHPASS=password))
    if r.returncode != 0 or not r.stdout:
        return False
    with open(local_path, "wb") as f:
        f.write(r.stdout)
    return True


def verify_db(path):
    """真备份还是空壳？连库跑完整性检查并数表。"""
    try:
        c = sqlite3.connect(path)
        ok = c.execute("pragma integrity_check").fetchone()[0]
        tables = c.execute(
            "select count(*) from sqlite_master where type='table'"
        ).fetchone()[0]
        c.close()
        return ok == "ok" and tables > 0, f"{ok}, {tables} tables"
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:120]


def main():
    password = pve_password()
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    tmp = os.path.join(BACKUP_DIR, ".tmp-" + stamp)
    os.makedirs(tmp, exist_ok=True)

    got = []
    for name in DB_FILES + EXTRA_FILES:
        if pull(password, f"{REMOTE_DATA}/{name}", os.path.join(tmp, name)):
            got.append(name)
    print("  pulled:", ", ".join(got) or "(nothing)")

    db = os.path.join(tmp, "db.sqlite3")
    if not os.path.exists(db):
        print("  [ERROR] db.sqlite3 missing — aborting")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1

    good, detail = verify_db(db)
    print(f"  verify: {detail}")
    if not good:
        print("  [ERROR] integrity check failed — keeping nothing")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1

    final = os.path.join(BACKUP_DIR, f"{SERVICE}-{stamp}.tar.gz")
    shutil.make_archive(final[:-7], "gztar", tmp)  # 'gztar', not 'gzip'
    print("  [ok] %s (%.1f KB)" % (os.path.basename(final),
                                    os.path.getsize(final) / 1024))
    shutil.rmtree(tmp, ignore_errors=True)

    files = sorted(f for f in os.listdir(BACKUP_DIR)
                   if f.startswith(SERVICE + "-") and f.endswith(".tar.gz"))
    for old in files[:-KEEP]:
        os.remove(os.path.join(BACKUP_DIR, old))
        print("  [clean] removed", old)
    print("  total backups:", min(len(files), KEEP))
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 4:
        CTID, REMOTE_DATA, SERVICE = sys.argv[1], sys.argv[2], sys.argv[3]
        BACKUP_DIR = f"~/.hermes/backups/{SERVICE}"
    sys.exit(main())
