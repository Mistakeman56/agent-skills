# MCP Server 部署到 CT <ID> (mcp-server LXC)

部署第三方 Python MCP 服务器到 CT <ID>（192.0.2.10，容器内 `/opt/mcp-venv`）并注册到 Hermes 的完整流程。2026-07-31 以 FlightTicketMCP (github.com/xiaonie7/FlightTicketMCP) 实战验证。

## 环境速查

| 项 | 值 |
|----|-----|
| CT <ID> IP | 192.0.2.10 |
| 通过 PVE 执行 | `sshpass -p 'PASS' ssh root@192.0.2.10 "pct exec 200 -- bash -c '...'"` |
| 直接 SSH | `sshpass -p 'PASS' ssh root@192.0.2.10 "..."`（同密码） |
| Python venv | `/opt/mcp-venv`（已有 fastmcp 3.2.4、uvicorn，但**没有 pip**！） |
| 系统 Python | `/usr/bin/python3`（3.11，有 pip，需 `--break-system-packages`） |
| 已有启动脚本 | `/opt/mcp-start-*.sh`（amap/github/ha 等） |

**关键坑：CT <ID> 的 venv 里没有 pip（`/opt/mcp-venv/bin/pip: No such file or directory`），但 `which fastmcp` 能找到。** 装依赖用系统 pip + `--break-system-packages`，跑服务用 `python3`（系统）或 venv python（如果依赖都在 venv）。FlightTicketMCP 最终是依赖全装进系统 Python、用 `python3 -m flight_ticket_mcp_server` 跑通的。

## 部署流程

### 1. 克隆仓库（GitHub 直连不通 → OpenClash 代理）

```bash
# 先确认 OpenClash 在跑（重启后可能 inactive！）
ssh -p 2222 root@192.0.2.10 '/etc/init.d/openclash status'   # 期望 running
# 如果 inactive：/etc/init.d/openclash start && sleep 5

# 在 CT <ID> 里用带认证的代理 clone（用户名 Clash，密码在 /etc/openclash/<config>.yaml 的 authentication 段）
pct exec 200 -- bash -c 'cd /opt && git -c http.proxy=http://Clash:hrFM183F@192.0.2.10:7890 -c https.proxy=http://Clash:hrFM183F@192.0.2.10:7890 clone --depth 1 https://github.com/OWNER/REPO.git'
```

**注意：代理要认证。** OpenClash 返回 407 时，在 `/etc/openclash/<当前配置>.yaml` 里 grep `authentication:` 找 `用户名:密码`。

### 2. 装依赖（pip 不要走代理！用清华源）

```bash
# 代理对 pip 返回 407 / SSL 反复断 —— 直接用清华源，实测远快于代理
pct exec 200 -- bash -c 'export http_proxy=http://Clash:hrFM183F@192.0.2.10:7890 https_proxy=http://Clash:hrFM183F@192.0.2.10:7890; \
  nohup pip install --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple <pkgs> > /tmp/pip_install.log 2>&1 & echo PID=$!'

# 大包（如 selenium 9.4MB）经代理下载会反复 SSL 断 → 必须 nohup 后台 + 清华源
# 装完后逐个验证：
for m in fastmcp pydantic requests dateutil pytz uvicorn fastapi DrissionPage selenium geopy; do
  python3 -c "import $m" 2>/dev/null && echo "$m OK" || echo "$m MISSING"
done
```

### 3. 打补丁（浏览器类 MCP 常见）

DrissionPage 在 LXC 里找不到 Chrome 时报 `BrowserConnectError: The browser connection fails. Address: 127.0.0.1:9222`。CT <ID> 有 `/usr/bin/google-chrome`，但 DrissionPage 不自动用。**在代码里显式指定：**

```python
co = ChromiumOptions()
co.set_browser_path('/usr/bin/google-chrome')
co.headless(True)
co.set_argument('--no-sandbox')
co.set_argument('--disable-gpu')
co.set_argument('--disable-blink-features=AutomationControlled')
co.set_user_agent('Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15')  # 伪装手机 UA
co.set_argument('--window-size=390,844')
self.page = ChromiumPage(co)
```

### 4. 创建启动脚本 + 注册 Hermes

```bash
# /opt/mcp-start-flight.sh
#!/bin/bash
export PATH="/usr/local/bin:$PATH"
export MCP_TRANSPORT=stdio
export MCP_DEBUG=false
cd /opt/FlightTicketMCP
exec python3 -m flight_ticket_mcp_server
```

注册到 `~/.hermes/config.yaml`（与现有 10 个 MCP 同一模式：mcp-compressor 压缩 + SSH 桥）：

```yaml
mcp_servers:
  flight:
    command: mcp-compressor
    args: ['--compression-level', 'max', '--server-name', 'flight', '--',
           'ssh', '-o', 'StrictHostKeyChecking=no', 'root@192.0.2.10', '/opt/mcp-start-flight.sh']
    timeout: 30
```

```bash
# 验证
hermes mcp list           # flight 应出现且 enabled
hermes mcp test flight    # ✓ Connected + Tools discovered
```

**注意：`hermes mcp test` 通过后，当前会话还看不到新工具**（工具在会话启动时注入）。新会话或 `/reload-mcp` 后才可用。

## ⚠️ 实测陷阱：爬虫类 MCP 打不过携程反爬

FlightTicketMCP 的核心功能（searchFlightRoutes）爬 `flights.ctrip.com`，**即使手机 UA + 反自动化标记也拿不到数据**（返回空页面/whaleguard，机房 IP 被识别）。curl 用手机 UA 能拿到 757KB 页面但那只是 JS 框架，航班数据要渲染后才有。

**结论：不要指望爬虫类 MCP 在 LXC 机房 IP 下绕过携程/去哪儿等强反爬站点。** 该 MCP 的以下功能仍可用：
- ✅ getWeatherByCity / getWeatherByLocation（Open-Meteo，免费 API）
- ✅ getFlightStatus / getAirportFlights（OpenSky Network，免费，晚间数据少属正常）
- ❌ searchFlightRoutes（携程反爬）
- ❌ getFlightInfo / getTransferFlightsByThreePlace（依赖浏览器爬取）

替代：查具体航班用用户手机上的携程/春秋 APP（见 china-domestic-travel-planning 技能）。
