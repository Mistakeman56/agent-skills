# 计算机网络知识库 — 完整参考示例

本文件记录2026-05-14建成的计算机网络知识库完整规格，作为「贴近用户实际运维环境的领域知识库」构建模板。

## 总体规格

| 指标 | 值 |
|------|-----|
| 文档数 | 21（20知识块 + 1知识图谱） |
| 段落数 | ~310 |
| 总大小 | 280KB |
| 总造价 | ¥0.83 |
| 存储路径 | `/root/rag-data/cn_network_blocks/` |
| 搜索工具 | RAG SimpleRAG（BM25关键词） |
| 研究工具 | BrightData（来源搜索+URL验证） |
| 并发策略 | 3路delegate_task并行（9+5+6路） |

## 模块结构

| 模块 | 条数 | 文件名前缀 | 来源数 |
|------|:----:|:----------:|:------:|
| 概述 | 1 | cn_network_overview | ≥2 |
| 物理层 | 2 | cn_physical_* | ≥2 |
| 数据链路层 | 5 | cn_datalink_* | ≥2 |
| 网络层 | 6 | cn_ip* / cn_routing* / cn_multicast* | ≥2 |
| 传输层 | 3 | cn_transport_* | ≥2 |
| 应用层 | 3 | cn_application_* | ≥2 |
| 知识图谱 | 1 | cn_knowledge_graph | — |

## 文件命名约定

```
cn_{module}_{topic}.txt
```

示例：
```
cn_transport_tcp_connection.txt   — 传输层 → TCP连接管理
cn_datalink_lan_switch.txt        — 数据链路层 → LAN与交换机
cn_application_dns.txt            — 应用层 → DNS域名系统
```

## ⭐ 关键创新：Homelab Context Embedding（用户真实环境嵌入）

**这是本知识库最大的特色，也是后续同类任务最值得复用的模式。**

计算机网络是用户每天都在亲手操作的技术领域（路由/NAT/子网划分/ARP/代理/TCP调优）。为了最大化知识库的复习价值，每个知识块都嵌入了用户**自己内网的配置场景**作为实际例子：

| 模块 | 嵌入的用户真实场景 |
|:----|:------------------|
| 网络层/子网 | `192.0.2.10/24` 内网结构、Fritzbox路由聚合、iStoreOS路由表 |
| 网络层/协议 | ARP嗅探(Cain实验抓到的MAC)、DHCP分配(路由器/iStoreOS)、私有地址NAT穿透(Clash映射) |
| 数据链路层/交换机 | 家庭交换机组网、`show mac-address-table`查看、VLAN隔离(IoT/主网) |
| 数据链路层/WiFi | 802.11漫游(办公室走路微信视频)、RTS/CTS干扰(咖啡厅WiFi拥堵) |
| 传输层/TCP | Clash代理TLS握手、v2raya `TIME_WAIT` 爆炸、校园网下载速度锯齿 |
| 传输层/丢包 | 移动网络假丢包导致TCP性能骤降、Tailscale直连打洞超时 |
| 应用层/DNS | Clash DNS分流、Tailscale DDNS、DNS污染/劫持、DoH配置 |
| 应用层/HTTP | CDN回源503故障、HTTPS 502 Bad Gateway排查、正向代理调试 |
| 应用层/FTP | FTP主动模式NAT不通、TFTP PXE超时 |

**效果：** 用户看到"这个我遇到过！现在知道原理了" → 知识留存率远高于纯理论描述。

**何时使用此策略：** 当用户说"这个跟我们天天折腾的项目最相关"或知识领域与用户的日常运维/配置/排障高度重合时，必须启用。

## 构建流程

### Phase 1：研究计划
- 基于408大纲拆分6大模块+知识图谱
- 按用户日常接触频率排优先级：网络层(6) → 数据链路层(5) → 传输层(3) → 应用层(3) → 物理层(2) → 概述(1)
- 计划中承诺「每条知识块结合用户内网实际场景举例」
- 输出 `research_plan.md`

### Phase 2：定向研究
- BrightData搜索中文408资料获取source_url
- 因为用户实际配置了内网，source_url可包含硬件厂商文档（华为交换机、iStoreOS等）和实战排障博客
- 输出 `research_notes.md`

### Phase 3：知识蒸馏（关键技术细节）
- **子Agent prompt设计（已验证的有效格式）：**
  1. 明确告知子Agent「你是一个计算机网络专家」
  2. 指定输出目录 `/root/rag-data/cn_network_blocks/`
  3. 逐条列出文件名+主题描述（内容要点概括）
  4. 嵌入完整17字段模板（包含字段描述和🔴标记，不能简化）
  5. 特别强调「结合实际用户场景举例」（给出具体场景方向：子网划分=192.0.2.10/24、TCP=Clash代理建连、DNS=Clash DNS分流、ARP=Cain嗅探实验）
  6. 提供至少3个可用source_url

- **子Agent prompt模板（可直接复用）：**
  ```
  你是一个{领域}专家，正在为{用途}构建RAG知识库。
  每条知识块必须AI理解后重写，详细说明至少800字，embedding_text至少300字。
  
  {结合实际场景的特别要求}
  
  需要生成以下{个数}个文件到 {输出目录}：
  1. {文件名}.txt — {主题描述}
  2. ...
  
  每条知识块必须包含以下完整17个字段：
  title/summary/core_concepts🔴/detailed_explanation/architecture_modules🔴/keywords/best_practices/limitations/common_problems/failure_cases🔴/edge_cases🔴/performance_bottlenecks🔴/related_concepts/source_url(≥2个)/confidence/applicable_scenarios🔴/embedding_text
  
  可用source_url: ...
  ```

### Phase 4：入库与验证
- 新增模块无需清空DB
- 调用rag_ingest逐文件入库（21个文件约22次调用）
- 验证策略：3个不同角度关键词
  - `"子网划分 CIDR 子网掩码 路由聚合"` → 验证网络层
  - `"TCP三次握手 四次挥手 拥塞控制 滑动窗口"` → 验证传输层
  - `"CSMA/CD 以太网 MAC地址 交换机自学习"` → 验证数据链路层

## 费用报告参考

| 来源 | 输入(token) | 输出(token) |
|:----|:----------:|:----------:|
| 子Agent1 — 网络层+物理层+概述 | 363K | 26K |
| 子Agent2 — 数据链路层 | 233K | 22K |
| 子Agent3 — 传输层+应用层 | 257K | 22K |
| 父Agent（研究+入库+验证） | ~200K | ~25K |
| **合计** | **~1,053K** | **~95K** |

**DeepSeek V4 Flash 成本：**
- 输入缓存命中 ~40%：~421K × ¥0.02/百万 = ¥0.01
- 输入缓存未命中 ~60%：~632K × ¥1/百万 = ¥0.63
- 输出：95K × ¥2/百万 = ¥0.19
- **总计：约¥0.83**

## 和OS知识库的对比

| 维度 | 操作系统 (OS) | 计算机网络 (CN) |
|:----|:-------------:|:---------------:|
| 文档数 | 22 | 21 |
| 造价 | ¥0.91 | ¥0.83 |
| 并发策略 | 3路delegate_task | 3路delegate_task |
| 特殊策略 | Canonical教材为主 | Homelab Context Embedding |
| 用户场景关联 | 中等（考研知识点） | 极高（天天实操的技术） |
| 代码示例 | 伪代码/地址转换 | 配置命令/wireshark抓包示例 |

## 最佳实践总结

1. **用户场景关联优先**：用户说自己"天天折腾"的领域 → 每条知识块必须嵌入至少1个用户真实环境例子
2. **子Agent prompt带完整模板**：17字段模板不能缩写、不能拆开给——一个prompt里直接全给
3. **优先级按实用度而非理论权重**：网络层(6条)排第一，因为用户天天折腾路由/NAT
4. **故障案例要真实**：failure_cases要用用户可能真实遇到的场景（NAT打洞失败、DNS劫持、TCP TIME_WAIT爆炸）
