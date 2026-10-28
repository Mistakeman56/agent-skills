# 国家电网用电数据接入 HA（选型 + 装法）

检索结论（装前请按仓库 README 复核一次）。

## 选型：按 HA 形态先过滤一刀

| 集成 | 形态 | 认证 | 判定 |
|---|---|---|---|
| `stevenjoezhang/hass-state-grid` | HACS 自定义集成 → `custom_components/` | 网上国网 手机号 + 密码 | **首选**：纯 API，不要浏览器/验证码 OCR/LLM |
| `ARC-MX/sgcc_electricity_new` | HACS 自定义集成 | 网上国网账号 | 备选：需要常驻 Playwright 浏览器 |
| `hanepudding` 系列 | **Add-on** | 账号密码 | **直接出局**：CT <ID> 是 Docker 形态，没有 Add-on 市场 |
| `renxiaoyaoo/ha-95598` | 独立容器 + Selenium + LLM | — | 不选：浏览器 + 模型的运维成本最高 |

过滤顺序：**先看形态能不能装，再看要不要常驻浏览器**。Add-on 类集成在 Docker 形态的 HA 上永远不可用，别花时间读它的文档。

## 前置条件

1. **网上国网账号**（手机号 + 密码）；没有就注册，或用「忘记户号」按用电地址反查。
2. **户号**：多数实现能从账号自动识别，一个账号可接多个户号。
3. CT <ID> 已装 HACS → 走 HACS 自定义仓库或手工落文件二选一即可。

## 装法（custom component 通用）

1. 取仓库的 `custom_components/<domain>/` → 放到宿主 **`/opt/ha-config/custom_components/<domain>/`**（宿主路径，不是容器内 `/config`）。
2. 重启 HA 容器：`sshpass -p <PVE_ROOT> ssh root@192.0.2.10 'pct exec 201 -- docker restart <容器名>'`（容器名以 `pct exec 201 -- docker ps` 为准，别猜）。
3. HA UI → 设置 → 设备与服务 → 添加集成 → 搜域名。
4. **账号密码由用户在 UI 自己输入**，不代输、不落聊天。
5. 回读验证：确认出现日/月用电量实体，且状态在变化（改动生效前的「已安装」不算数）。

## 实体怎么用才不白装

- 电量类（日/月用电量）要挂 **`total_increasing`** 统计 → 才能进 HA Energy 面板出日/月曲线与费用。
- 主指标只认**用电量**；账户余额、本年累计是辅助。
- 多户号按户号分组，别混进同一个统计。

## 未完成项

**状态：未实施**（等网上国网账号/户号）。装完必须做的一次性验收：**连续两天把日用电量与网上国网 App 的显示对齐**，对不上就先查接口口径（自然日 vs 结算日），别急着做曲线和费用看板。
