# 小主机角色分配与集群判断

场景：手上一台闲置迷你主机（N5095 / J4125 一类，4 核 8G），用户问「能不能跟现有 PVE 组集群」
或「装什么系统」。**先定角色，再谈技术栈**——多数情况下正确答是「不组集群」。

## 先看现役 PVE 是什么状态

```sh
pveversion; pvecm status 2>&1 | head -4; free -g | sed -n 2p; nproc
qm list | tail -n +2 | wc -l; pct list | tail -n +2 | wc -l
pvesm status | head -6
```

`Corosync config '/etc/pve/corosync.conf' does not exist` = 单机、没集群。
这个读数加上 VM/CT 数量，直接决定「要不要集群」的答案。

## 两台机器不要组集群（家庭环境的默认结论）

1. **quorum 陷阱**：默认 2 节点 = 2 票，需要 2/2 才可写。**重启任意一台，另一台立刻失去 quorum，
   连启 VM 都不行**——比单机还脆弱。绕开要加第三台仲裁设备（QDevice，可跑在 CT 或 NAS 上），
   等于多一个要维护的东西。
2. **没有共享存储 ⇒ HA 是空的**：本地 `local-lvm` 只能离线迁移（关机搬盘），
   HA 自动接管要求 Ceph/NFS/iSCSI，而 Ceph **3 节点起步**。2 台直接出局。
3. **收益配不上成本**：负载只有 1 台 VM + 6 个 CT 时，机器坏了手动切过去就行，
   不需要秒级接管。集群给的是统一管理和在线迁移，这个规模下不值。

结论口径：**不组集群，独立装**；真想要 HA 等第三台机器到了再谈 Ceph。

## 装什么系统（专机跑容器的场景）

| 方案 | 常驻内存 | 判断 |
|---|---|---|
| Debian minimal + Docker | ~0.4 G | ✅ 首选 |
| Ubuntu Server + Docker | ~0.8 G | ✅ 可 |
| PVE | ~1.5 G | ❌ 不做虚拟化时白吃 1/5 预算 |
| 桌面发行版（deepin DDE 等） | ~1.2–1.5 G | ❌ 专机做服务器不该带桌面 |

安装时**软件选择只勾「SSH server」**，桌面环境、standard utilities、web server 全不勾；
分区用「整个磁盘 + 单一分区」；问「是否使用网络镜像源」选**否**（装好后统一换国内源）。

8 G 内存的账：系统 0.4–0.5 G + 一个 4 G 上限的重容器 ≈ 还剩 3.5 G，够再放几个轻量服务
（IT-Tools / Uptime Kuma / FileBrowser / Vaultwarden 各 100 M 级）。
**专机专用时不必为省内存选功能残缺的 lite 镜像**——那是给「与存储服务共享内存的 NAS」准备的取舍。

## 这台小盒子能不能当主路由

- **≥2 个千兆口** → 可当主路由（PPPoE + NAT）；**≥1×2.5G WAN + 2×2.5G LAN** 才配得上 2000M 家宽。
- **只有 1 个口** → 别当主路由。单臂路由要 VLAN 单线复用，绕；而且千兆口本身就是 ~940 Mbps 的硬顶，
  2000M 宽带用不上。
- 性能参照：**N5095（Jasper Lake，4 核 2.0–2.9 GHz）比现役 J4125（Gemini Lake Refresh，4 核 2.0 GHz）
  高约 30–40%**，8 G 内存跑 PPPoE + NAT 绰绰有余——先盘手上闲置硬件，再谈买新的。
- 真要做双机对照（主路由 vs 现役软路由），摆放方式与判读标准见 speedtest-triage 的
  「换路径对照实验」一节，别在这里另写一套。
