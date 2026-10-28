# 案例：Magpie Experimental（大力喜鵲）—— 双卡 / 跨厂判定

一次典型的"用户被短视频/论坛种草 → 让你核实项目到底行不行"的任务。留下**架构性结论**，
数值（版本号、star、下载量）一律现场查。

## 项目锚定

- 用户口中的 "magpie experimental" = **`SAOG0721/Magpie`**，繁中圈昵称「**大力喜鵲**」。
- 是 **`Blinue/Magpie`（14.7k★，Windows 窗口超分工具）的非官方实验 fork**，默认分支 `experimental`。
- 坑：`magpie` 同名项目至少有四个 —— 窗口超分工具、一门"实验性编程语言"（`magpie-lang/magpie`）、
  LLM 数据合成框架（`magpie-align/magpie`）、一个 experimental MC 客户端。
  **搜索引擎给出的三个候选都不是用户要的那个**；真正的仓库名藏在**论坛帖的 HTML 超链接**里
  （`web_extract` 会把链接目标丢掉，只剩"GITHUB連結"几个字）。
- 首次定位靠社区帖（巴哈姆特），复核靠 GitHub REST API。

## 它是什么（稳定）

窗口**捕获 + 后处理**工具：抓取目标窗口画面，再套效果链 —— DLSS SR / DLSS FG（帧生成）/
DLSSNR（神经渲染）/ FSR 2·3·4 / XeSS / XeSSFG / RTX Video / Smooth Motion。
因为它**不参与游戏渲染**，所以"渲染用的卡"和"跑效果的卡"可以不是同一张。

## 为什么"双卡分工"成立（代码级证据）

| 机制 | 证据位置 | 含义 |
|---|---|---|
| 每档可绑定一张卡 | `include/ScalingOptions.h`（`idx` 为显卡索引，`vendorId`/`deviceId` 校验不匹配则枚举查找）、`DeviceResources.cpp` 按 VendorId+DeviceId 枚举匹配、`Renderer.cpp` 启动打印"当前图形适配器" | **游戏在 A 卡渲染、Magpie 指定在 N 卡处理** —— 官方机制 |
| 光流引擎二选一 | `MotionVectorRequest.h`：`OpticalFlowMethod { None, Amd, Nvidia }` | 效果参数 `opticalFlowMethod` 决定用哪家的光流 |
| "AMD OF" 是**厂商中立算法** | `AmdOpticalFlowProvider.h` 注释原文：`"Cross-vendor FidelityFX Optical Flow provider. 'AMD OF' identifies the algorithm, not a vendor restriction: any D3D12 adapter satisfying the shader-model, wave-op and format requirements may create it."`；日志串 `vendorIndependent=true` | 名字叫 AMD，**任何 D3D12 卡都能跑** |
| NVOF 是硬门 | `NvidiaOpticalFlowProvider.cpp:462` `if (adapterDesc.VendorId != 0x10DE) { /* 拒绝 */ }` | NVIDIA 光流**只认 N 卡** |
| DLSS 本体要 N 卡 | 走 NVIDIA NGX（同一 `VendorId` 门） | **跑 DLSS 的那张卡必须是 N 卡**，A 卡跑不了 DLSS 本身 |
| XeSS 有跨厂路径 | `XeSSUpscaler.h` / `.cpp:224`：cross-vendor path 需 **SM 6.4 / DP4a**；Intel Arc 另有 x2–x4 多帧生成 | 非 Intel 卡也能 x2 |
| 光流共享池 | `MotionVectorRequest.h` 的 `FrameGuidanceRequirements` 注释：*"select one shared provider: **NVOF first, AMD second**; highest REQUESTED quality"* | 一个效果组里多个效果**共用一份光流**，只算一次 |

## 判定模板（这种"能不能跨厂"的问题照这个说）

```
✅ 原理成立：渲染卡与处理卡可分离（捕获后处理架构 + 每档绑定显卡）
✅ 光流可跨厂：用 "AMD OF"（FidelityFX，vendorIndependent）
⛔ 硬性边界：DLSS 本体必须 N 卡（NGX）
⚠️ 官方只实测过 N+N（5070 渲染 + 5080 神经渲染）；"A 卡渲染 + N 卡 DLSS" 未被作者验证 → 原理成立、需自己趟坑
```

## 使用代价 / 概念纠正

- **输出画面必须显示在"跑后处理那张卡"所接的显示器上**（社区实测帖明确说明）。
- 跨适配器要拷贝画面 → **PCIe 带宽/延迟成本**，没被文档量化。
- **不是"交火"**：SLI/CrossFire 是两卡同算一帧（已淘汰）；这是**流水线分工**。
  社区血脉是"小黄鸭"（Lossless Scaling）先做的双卡补帧，Magpie Experimental 把它做到 DLSS 层面。
- **画质天花板**：拿不到引擎的动态矢量/深度/曝光/独立 UI，光流全靠**从颜色帧估算**
  （作者在 handoff 文档里自己写了 "光流由捕获颜色帧估算，不是引擎 MV"）→ 拖影、文字/HUD 不稳。
- **生成的帧 ≠ 真帧**，不等于输入延迟改善。

## 其它值得照实说的点

- 迭代极快（一个月十几个 `-experimental` 版本），作者要求**每次删旧目录重装，不能覆盖**。
- 会**替换 NVIDIA DLL**（附件提供官方版 / RTX 40-50 社区兼容版）并附 `NGX_OTA_Switch.bat`
  改**系统级 NGX OTA** 设置 —— 属于要提前告知的风险。
- 打包里含 NVIDIA 专有组件，作者自己的许可证文档写明 GPLv3 与专有组件组合分发"存在未解决风险"。
- `DLSSNR` 需要 RTX **40/50** 系（RTX 40 是 Ada，带 OFA 光流加速器）。

## 复用命令

```bash
# 元数据 + 版本节奏 + 一手文档目录
curl -s -H "Accept: application/vnd.github+json" https://api.github.com/repos/SAOG0721/Magpie
curl -s -H "Accept: application/vnd.github+json" "https://api.github.com/repos/SAOG0721/Magpie/releases?per_page=10"
# 能力判定：clone 后 grep 硬门
git clone --depth 1 --branch experimental --single-branch https://github.com/SAOG0721/Magpie.git
grep -rn -i -e "cross-vendor" -e "vendorIndependent" -e "0x10DE" -e "AMD OF" <clone>/src <clone>/docs
```
