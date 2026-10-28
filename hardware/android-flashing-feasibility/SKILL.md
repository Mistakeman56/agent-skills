---
name: android-flashing-feasibility
description: "Use when 判断安卓手机能不能刷机/解 bootloader、能刷什么 ROM。"
version: 1.0.0
author: Hermes Agent
license: MIT
---

# 安卓手机刷机可行性判断

用户拿来一台旧手机问「能不能刷」时，**先判断能不能，再谈怎么刷**。绝大多数「老手机想刷机」的结局是刷不了；早说结论比陪着一层层试更省时间，也避免用户先拆机再发现白拆。

## 判断顺序（照这个顺序走，别跳）

**① 芯片 → ② 系统/Android 版本 → ③ 开源解锁方案支持矩阵 → ④ 有没有可刷的 ROM → ⑤ 才谈操作**

第 ④ 步最容易漏、也最关键：**解锁 ≠ 能刷**。解锁成功却没有任何还在维护的 ROM，等于白折腾还多一次变砖风险。

## 华为/荣耀：2018 年后基本全锁死

- **2018-05 起官方停发解锁码**，官网下线。
- **Android 10+ 起 `fastboot oem unlock` 命令被整个移除**。
- **HarmonyOS 4.2+ 有 anti-rollback 熔丝**，连降级刷机也堵死。

| 芯片 | 开源解锁 | 现实方案 |
|---|---|---|
| Kirin 620/650/655/658/659/925/935/950/960 | ✅ | **PotatoNV**（免费开源）|
| Kirin 970 | ❌ | 只有 HCU-Client（RSA 私钥在其手里）|
| **Kirin 710 / 710A / 710F** | ❌ | **无解**：fastboot 里的 RSA 公钥与付费工具的私钥不匹配，官方解锁码也**只在 Android 10 以下有效** |
| Kirin 980 | ❌ | 同上 |
| Kirin 810 / 985 / 990 及更新 | ❌ | 无解 |

**PotatoNV**（`mashed-potatoes/PotatoNV`）原理：拆机短接 testpoint → 进 VCOM/工厂模式 → 往 **RAM** 里传一个出厂即解锁状态的板级 bootloader → 写入自定解锁码。**bootloader 只刷进内存，刷错不会变砖**，这是它最大的优点；代价是要拆机。它的 README 明确列出不支持的芯片，**先查这张表再拆机**。

## 关键现实：解锁了也没有 ROM 可刷

- **OpenKirin**（当年唯一正经的华为 AOSP 方案）**2018–2019 年就停了**，官网已下线，只覆盖 EMUI 8 时代约 17 款机型，做出来的是 **Android 8/9** —— 比现在手机自带的系统还旧。
- **LineageOS 官方没有华为设备**；postmarketOS 只支持极个别老机型。

**结论模板**：老华为的合理归宿不是刷机，而是「**root / 卸预装 / 当常驻设备**」。

## 不需要 root 的实用替代（先给这个）

```bash
adb shell pm uninstall --user 0 <包名>        # 卸载预装，效果接近 root
adb shell cmd package install-existing <包名>  # 后悔可恢复
```

HarmonyOS/EMUI 允许对当前用户卸载系统应用。**这比刷机收益高、风险几乎为零**，先清预装再谈其他。

大电池老机型（5000–6000 mAh）最适合当**常驻设备**：Home Assistant 面板、电子相框/时钟、监控屏、Termux 小型服务——插着电半个月不心疼，比任何开发板划算。

## 付费工具：别买

HCU-Client（约 $55）、DC-Unlocker、ChimeraTool 对 Kirin 710A 这类芯片的实测输出是 `Write FBLOCK for this model not supported, skipped!`。它们能做的是 **FRP / 华为 ID 解除、改 OEMInfo**（维修用途），**不等于 bootloader 解锁**，装不了第三方 ROM。**用户想刷机时明确劝退，别让他花这钱。**

## 真想刷机该买什么

- **二手 Pixel**（3/4/5 几百块）→ GrapheneOS、LineageOS 官方支持，`fastboot flashing unlock` 一条命令搞定。
- **二手小米/红米 Note 系列** → 社区最活跃，ROM 最多。
- **一加旧款** → LineageOS 支持好。

## 交付方式

先查型号（`设置 → 关于手机` 看型号 + 处理器 + 系统版本，或让用户发截图），**一次给结论**：能不能解 → 要不要拆机 → 解锁后有什么可玩 → 不能刷的话给替代玩法。**别让用户先拆机再发现白拆。**
