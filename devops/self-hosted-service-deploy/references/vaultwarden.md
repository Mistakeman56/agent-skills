# Vaultwarden（自建密码库）

## 部署要点

- 镜像 `vaultwarden/server:latest`，单容器，`-v /opt/vaultwarden/data:/data`，`-p 8080:80`
- **`DOMAIN` 必须写实际访问地址（含端口）**，客户端拿它拼 api / identity / notifications 端点；写错会导致客户端登录失败
- 实测 idle 16 MB 内存，1 核 1G 的 CT 绰绰有余
- 用户数据全在 `data/db.sqlite3`（表 `users`、`ciphers`）；`users` 的时间列叫 `created_at`，**没有 `createdAt`**

## 注册策略（易漏）

1. 首次要let the user 自己建号（主密码是零知识加密的唯一钥匙，**不能代设**，服务端也看不到）→ 临时 `SIGNUPS_ALLOWED=true`
2. 建完立刻 `docker rm -f` + 带 `SIGNUPS_ALLOWED=false` 重跑
3. **验证注册真关了不能只看 `/api/config` 的 `featureStates['disable-user-registration']`** —— 它和 `SIGNUPS_ALLOWED` 不是直接对应的（开关为 false 时该字段仍报 False）。可靠判据：
   - 登录页上 `Create account` 链接消失
   - 数据库 `select count(*) from users` 没有新增
   - 直接访问 `#/signup` 仍会渲染表单（前端路由行为），**不代表服务端放行**
4. `ADMIN_TOKEN` 明文会有启动警告；要上生产就用 `vaultwarden hash` 生成 Argon2 PHC 字符串

## 客户端接入

- 网页：`https://pass.example.com:18443`
- 手机/电脑：装**官方 Bitwarden 客户端**，登录页齿轮里填自建服务器 URL
- 从 Chrome 迁移：Chrome → 设置 → 密码管理器 → 导出 CSV → 密码库「工具 → 导入数据 → Chrome (CSV)」→ **导完立刻删 CSV**

## 报告页说"密码暴露几百/几千万次"不是站点不安全

查的是 **HIBP（Have I Been Pwned）Pwned Passwords**：客户端对密码做 SHA-1，**只发前 5 位**，服务端返回该前缀下全部后缀，设备本地比对（k-anonymity）—— **完整密码和完整哈希不出设备**。

数字含义是"该密码在公开泄露库里出现过多少次"，反映**密码本身**的强度，与自建服务是否安全无关。用户容易误解成"你写的网站有漏洞"，要先解除这个误解。

用同一套 API 复现有说服力：

```python
import hashlib, urllib.request
h = hashlib.sha1(pw.encode()).hexdigest().upper()
op = urllib.request.build_opener(urllib.request.ProxyHandler(
    {'https': 'http://127.0.0.1:7899', 'http': 'http://127.0.0.1:7899'}))
body = op.open(f"https://api.pwnedpasswords.com/range/{h[:5]}", timeout=25).read().decode()
count = next((int(l.split(':')[1]) for l in body.splitlines() if l.split(':')[0] == h[5:]), 0)
```

量级参考：`123456` ≈ 2.1 亿、`password` ≈ 5200 万、`admin` ≈ 4200 万、`P@<PASSWORD>` ≈ 642 万。8 位带符号的常见弱口令都在百万级。

**暴露 0 次只说明"不在公开库里"，不代表强度够** —— 9 位数字混字母仍建议换 4-5 词短语密码；并推 2FA，因为密码泄露后唯一还挡得住的就是第二因素。
