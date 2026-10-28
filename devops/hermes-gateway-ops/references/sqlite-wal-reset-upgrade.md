# SQLite WAL-reset bug 修复（Debian 12 实测，2026-08）

## 背景

`hermes doctor` 报 WAL-reset bug 风险：
- 系统 SQLite 3.40.1（Debian 12 bookworm 自带，apt 里没有更新版）
- `state.db`（~1GB，会话历史）和 `kanban.db` 都开 WAL 模式
- 修复版本：3.51.3+ / 3.50.7 / 3.44.6（见 https://sqlite.org/wal.html#walresetbug）

## 方案：编译官方新版到独立目录 + ldconfig 优先加载

不动系统库（apt 升级不冲突），Python 的 `_sqlite3` 模块动态链接 `libsqlite3.so.0`，通过 `/usr/local/lib` 软链 + ldconfig 让它默认加载新版。

## 步骤（完整可复现）

```bash
# 1. 查最新版本号（下载页有 PRODUCT 行：sqlite-autoconf-XXXXXXX.tar.gz）
curl -sL --noproxy '*' https://www.sqlite.org/download.html | grep -oE 'sqlite-autoconf-[0-9]+\.tar\.gz' | sort -u | tail -1
# 2026-08 最新是 3530400 = 3.53.4

# 2. 下载（注意年份路径！2026 年版本在 /2026/ 目录，不是 /2025/）
cd /tmp
curl -sL --noproxy '*' -o sqlite-autoconf-3530400.tar.gz \
  "https://www.sqlite.org/2026/sqlite-autoconf-3530400.tar.gz"

# 3. 解压编译（安装到 /opt/sqlite 独立目录）
tar xzf sqlite-autoconf-3530400.tar.gz
cd sqlite-autoconf-3530400
./configure --prefix=/opt/sqlite
make -j$(nproc)
make install

# 4. 软链到 /usr/local/lib（ldconfig 标准路径）
ln -sf /opt/sqlite/lib/libsqlite3.so.3.53.4 /usr/local/lib/libsqlite3.so.0
ln -sf /opt/sqlite/lib/libsqlite3.so.3.53.4 /usr/local/lib/libsqlite3.so
echo "/usr/local/lib" > /etc/ld.so.conf.d/local-lib.conf
ldconfig

# 5. 验证（无 LD_LIBRARY_PATH 也应生效）
python3 -c "import sqlite3; print(sqlite3.sqlite_version)"   # → 3.53.4
ldd /usr/lib/python3.11/lib-dynload/_sqlite3*.so | grep sqlite
# → libsqlite3.so.0 => /usr/local/lib/libsqlite3.so.0

# 6. 数据库完整性检查（旧库文件用新库打开）
python3 - << 'EOF'
import sqlite3
for db in ['~/.hermes/state.db', '~/.hermes/kanban.db']:
    conn = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    print(db.split('/')[-1], 'integrity=', conn.execute('PRAGMA integrity_check').fetchone()[0])
    conn.close()
EOF
# → integrity=ok

# 7. 清理临时文件
rm -rf /tmp/sqlite-autoconf-3530400* /tmp/sqlite-check.html
```

## 关键坑

1. **年份目录**：下载路径是 `https://www.sqlite.org/<年份>/sqlite-autoconf-<版本>.tar.gz`。用错年份（如 /2025/ 下 3.53.x）返回 404（189 字节 HTML），先 grep 下载页拿真实链接。
2. **别覆盖系统库**：软链到 `/usr/local/lib` 而不是替换 `/lib/x86_64-linux-gnu/libsqlite3.so.0`，apt 升级不冲突，回滚只需删软链 + ldconfig。
3. **Python 无需重新编译**：`_sqlite3.cpython-311-x86_64-linux-gnu.so` 动态链接 `libsqlite3.so.0`，ldconfig 后自动加载新库。
4. **版本号确认**：`3.53.4` ≥ `3.51.3`，满足修复要求。

## 已完成的机器（2026-08-18）

- CT <ID>（Hermes 主机）：/opt/sqlite + /usr/local/lib 软链已配好，Python sqlite3 = 3.53.4
- 下次 `hermes doctor` 应不再报 WAL-reset bug；无需重做
