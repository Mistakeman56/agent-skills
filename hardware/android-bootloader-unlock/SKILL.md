---
name: android-bootloader-unlock
description: Use when the user 问旧手机能否刷机/解锁 bootloader。
---

# 安卓手机能不能刷：解锁可行性判定

the user 手上会有闲置旧机，问「这个能不能刷」。**结论取决于芯片和底层 Android 版本，不取决于型号名字**。先拿这三个值再开口：

1. 设置 → 关于手机 → **处理器型号**（HiSilicon Kirin / 骁龙 / 天玑）
2. **当前系统**（EMUI 几 / HarmonyOS 几 / MIUI 几）——注意换算成底层 **Android 大版本**
3. 具体型号号（如 `MGA-AL40`、`PRA-AL00`），用来查是否有已知 testpoint / 解锁方案

## 华为 / 荣耀：先看芯片，几乎全死

**时间线背景**：官方解锁码网站 2018 年下线；**Android 10+ 的 fastboot 直接移除了 `oem unlock`（userlock）命令**；HarmonyOS 4.2+ 再加 anti-rollback 熔丝。所以「有解锁码」也可能已经无效。

| 芯片 | 开源解锁 | 说明 |
|---|---|---|
| Kirin 620 / 650 / 655 / 658 / 659 / 925 / 935 / 950 / 960 | ✅ | **PotatoNV**（`mashed-potatoes/PotatoNV`），唯一免费开源方案 |
| Kirin 710 / 710A / 710F / 970 / 980 | ❌ | 公钥与付费工具不匹配，**写不进新解锁码**；即使拿到码，**Android 10 以上也不生效** |
| Kirin 810 / 985 / 990 及更新 | ❌ | 无解 |

**PotatoNV 原理**：拆机短接 testpoint → 进 VCOM/BootROM → 把**板级工厂 bootloader 只刷进 RAM** → 借它往 nvme 分区写自己设的解锁码。因为只上 RAM，**刷错不变砖**，代价是要拆机。

**不要建议付费工具**：HCU-Client / DC-Unlocker 对 Kirin 710A 实际日志就是 `Write FBLOCK for this model not supported, skipped!`，最多做 FRP/网络锁，**不等于 bootloader 解锁**（ChimeraTool 的 bootrom 模式同理，是维修不是刷机）。

### 快速否决

型号属 **畅享/麦芒等 2020 年后千元机**（多为 Kirin 710A + HarmonyOS 3/4）→ **直接说刷不了，别拆**。HarmonyOS 3.0 底层是 Android 12，早已越过 Android 10 那条死线，且叠加熔丝。

## 解锁 ≠ 有得刷（第二道关，务必先说）

**华为系的第三方 ROM 生态已经死了**：OpenKirin 2018–2019 停更、官网下线只剩 archive.org；LineageOS 官方**完全没有华为设备**。即使解锁成功，能刷上的也是 Android 8/9 时代的旧系统，**比现系统还旧**。

所以老华为的务实归宿是下面「不刷也能做的事」，不要为了「刷个新系统」去拆机。

## 真要刷：推这些机器

- **二手 Pixel**（3/4/5）→ GrapheneOS / LineageOS 官方支持，`fastboot flashing unlock` 一条命令
- **二手小米 / 红米 Note** → 社区 ROM 最多
- **一加旧款** → LineageOS 支持好

## 不刷也能榨干旧机（无 root 也成立）

- **ADB 卸预装**，效果比 root 干净且可逆：
  ```bash
  adb shell pm uninstall --user 0 <包名>
  adb shell cmd package install-existing <包名>   # 恢复
  ```
- **当常驻设备**：大电池机型（如 6000mAh）插电不心疼，比开发板划算——Home Assistant 面板、监控屏、电子相框、Termux 小服务器、长辈机。

## 交付口径

- **能给明确「不能」就给明确「不能」**，并说清是哪一层拦住的（芯片不支持 / Android 版本过高 / 熔丝），比含糊「可能有难度」有用。
- 不要因为「技术上也许有 bootrom 漏洞在研究中」就留幻想口子。
