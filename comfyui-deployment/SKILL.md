---
name: comfyui-deployment
description: Windows 装 ComfyUI、修 GGUF/CUDA 出图报错时用。
---

# ComfyUI Windows 部署（Qwen-Image 2.1 无审查版实战）

2026-09-25 在 PC `<PASSWORD>`(192.0.2.10, 用户 <PASSWORD>, RTX 4080 SUPER 16G) 落地，全链路已验证出图。

## 目标文件
| 部件 | 文件 | 大小 | 位置 |
|---|---|---|---|
| DiT | `qwen-image-2.1-UC-Q6_K.gguf` | 5,876,556,576 | `models/diffusion_models/` |
| 文本编码器 | `qwen3vl_8b_int8_convrot.safetensors` | 9,350,798,360 | `models/text_encoders/` |
| （备用）Heretic GGUF | `qwen3vl_8b_heretic-Q4_K_M.gguf` | 5,027,785,376 | **不能用，见坑 7** |
| VAE | `qwen_image_2.1_vae_bf16.safetensors` | 675,509,688 | `models/vae/` |

仓库：`abenzerps/Qwen-Image-2.1-Uncensored-GGUF`（DiT/VAE/safetensors TE）、`pottokao/Qwen-Image-2.1-Text-Encoder-Heretic-GGUF`（Heretic）

## 工作流（API `/prompt` 格式，已验证可出图）
```
1 UnetLoaderGGUF   unet_name=qwen-image-2.1-UC-Q6_K.gguf
2 CLIPLoader       clip_name=qwen3vl_8b_int8_convrot.safetensors, type=qwen_image, device=default
3 VAELoader        qwen_image_2.1_vae_bf16.safetensors
4/5 CLIPTextEncode (positive/negative) ← clip[2]
6 EmptySD3LatentImage 1024x1024
7 KSampler  steps=20 cfg=4.0 euler/simple
8 VAEDecode → 9 SaveImage
```
**必须用原生 `CLIPLoader` + safetensors**，不能用 `CLIPLoaderGGUF`（见坑 7）。
一张 1024x1024/20 步 ≈ **72~80 秒**。

## 10 个坑（按踩到顺序）

1. **Windows SSH 跑多行 PowerShell 必须用 `-EncodedCommand`**（UTF-16LE → base64）。直接传脚本会被引号搞崩，报「命令行太长」或语法错。
2. **PowerShell here-string/复杂引号在 SSH 里必挂** → 一律「本地写文件 → scp 到无空格路径（`D:\ComfyUI\_dl\`）→ PowerShell 复制到目标」。scp 目标路径**不能用引号包裹带空格的路径**。
3. **SSH 拉起的进程随会话关闭被杀** → 必须用 `schtasks /Create /TN X /TR ... /SC ONCE /ST 23:59 /F` + `schtasks /Run`。**开机自启用启动文件夹** `C:\Users\<PASSWORD>\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\ComfyUI.vbs`（`schtasks /RU 用户 /RP 密码` 会报「用户名或密码不正确」，别试）。
4. **杀进程的匹配式必须用 `*main.py*`**，不能用 `*ComfyUI\main.py*`（启动时用 `-WorkingDirectory` + 相对路径 `main.py`，命令行里没有 `ComfyUI\`）。匹配错 = 没真重启 = 补丁不生效（这次浪费 3 轮）。
5. **HF 下载走 OpenClash 代理会中途卡死**（进程活着、文件不涨）。解法 = **短连接循环**：`curl -L -C - --connect-timeout 15 --max-time 90 --speed-limit 61440 --speed-time 20 -sS -o 文件 URL`，外层 `while` 判断字节数达标才退出。峰值 **19.95 MB/s**（单连接长传只有 1.45）。
6. **`urllib` 通过代理只有 20 KB/s，`curl` 有 7 MB/s** → 任何下载都用 curl，别写 Python urllib 下载器。主源用 **`hf-mirror.com`**（国外 HF 官方源更慢且更容易 stall）。
7. **Heretic 文本编码器 GGUF 是 llama.cpp 原始 key**（`token_embd`、`blk.0.attn_k`），ComfyUI 判定 TE 要的是 `model.language_model.layers.0.input_layernorm.weight` → 对不上 → 走岔分支输出 12288 维，DiT 要 4096 → `KSampler` 报 `normalized_shape=[4096] ... got [2,512,12288]`。**换仓库里的 `qwen3vl_8b_int8_convrot.safetensors`（9.35 GB）走原生 CLIPLoader 即可**，ComfyUI 0.37 原生支持 convrot/int8 量化。
8. **ComfyUI-GGUF 节点（city96）不认识 `qwen_image21` 架构** → `loader.py:12` 的 `IMG_ARCH_LIST` 加上 `"qwen_image21", "qwen_image2"`（先备份 `loader.py.bak.<时间戳>`）。报错 `Unexpected architecture type in GGUF file: 'qwen_image21'`。
9. **pip 从阿里镜像装到的是 `torch 2.14.0+cpu`** → 必须显式指定 CUDA 源：`pip install torch==2.14.0+cu126 torchvision --index-url https://download.pytorch.org/whl/cu126`（该源 2.6GB 只花 38 秒，**77.9 MB/s，比 HF 快得多**）。验证：`torch.cuda.is_available()` 必须 `True`。
10. **期望文件大小要用 HEAD 拿真实字节数**，别手估。我估多了 43,424 字节 → `$sz -ge $target` 永不满足 → **死循环空转 80 轮**，下一个文件根本没开始下。

## 🔑 官方参数（Comfy-Org 模板原文，2026-09-26 核实）
```
KSampler: steps=25, cfg=1, sampler=euler, scheduler=simple, denoise=1
text2image / image_edit 两个模板都是这套
文本编码节点: TextEncodeQwenImage21   ← 不是 CLIPTextEncode！
  widgets = [prompt, negative_prompt, max_length=1024]
图生图: LoadImage → TextEncodeQwenImage21 的 image_1..image_10 槽位  ← 不是 VAEEncode+denoise！
其他节点: QwenImage21Cache["auto","default"] / ComfySwitchNode[false] / EmptyLatentImage
```

**cfg 必须 = 1**：官方模板注释原文 `cfg: keep 1 for the Qwen Image 2.1 official path.`
`negative_prompt: unused while cfg is 1.` —— **cfg>1 时才启用负向分支，高 cfg 出糊且让提示词跟不住**
（德语实测：「Wer aus Gewohnheit cfg 7 einstellt, bekommt Matsch」）

**踩过的坑（2026-09-26）**：曾给用户 cfg=4.0/5.0 + steps=20 + CLIPTextEncode + SD 时代 img2img 旁路 →
用户反馈「感觉还是有审查」，实为**参数/节点错**导致提示词不被遵循，**不是真审查**。

**denoise 曲线**（latent img2img 旁路）：0.5 贴近原图 / 0.6 基本改不动 / 0.8 改动明显 / >0.8 接近全重画。

**改造清单**：CLIPTextEncode→TextEncodeQwenImage21；cfg→1；steps→25；负向清空；
图生图整条 LoadImage→VAEEncode→denoise 换成参考图进 image_1 槽位、denoise→1。

**✅ 2026-09-26 实测验证通过**（换成这套后，之前加不上的红贝雷帽/暖光/散景全部加上了）：

**API 格式（/prompt）里参考图的写法** —— 是 `images.image_1` 而不是 `images`：
```json
"5": {"class_type":"LoadImage","inputs":{"image":"xxx.png"}},
"6": {"class_type":"TextEncodeQwenImage21","inputs":{
       "clip":["3",0], "prompt":"...", "negative_prompt":"", "resolution":1024,
       "images.image_1":["5",0] }}
```
（试过 `images:[[...]]` 和 `images:[...]` 都不对，只有 `images.image_1` 能过）

**TextEncodeQwenImage21 规格**（object_info 实测）：
- 输入: `clip, prompt, negative_prompt, resolution(INT), images(COMFY_AUTOGROW_V3)`
- 输出: `['CONDITIONING','CONDITIONING','LATENT']` → `positive / negative / latent`
  ⚠️ 但官方模板的 latent 走 `EmptyLatentImage`，**没用**它第三个 latent 口

**实测速度**：文生图 cfg=1 用 48 秒（cfg=4 时 64~72 秒，省掉 uncond 那一遍）；图生图 152 秒。

**偷懒方案**：直接用官方模板 JSON，只改 3 个模型文件名
（`UNETLoader`→`UnetLoaderGGUF`+`qwen_image_2.1-Q6_K.gguf`、`CLIPLoader` clip→Heretic）。但官方模板是 subgraph 结构（含可选 PE 提示词改写路径），自己搭平面工作流更可控。

## ⚠️ ComfyUI-GGUF 必须用 leejet fork（2026-09-26 换装）
```
city96/ComfyUI-GGUF   ← 原版停在 2026-01-12，不认 qwen_image21，需手打补丁 ❌
leejet/ComfyUI-GGUF   ← 教程指定，loader.py 原生含 "qwen_image21" ✅ 当前在用
molbal/ComfyUI-GGUF   ← 另一个实测可用的 fork（earngenix 教程用的）
```
教程：https://hoangyell.com/qwen-image-2-1-uncensored-comfyui/
      https://www.earngenix.com/tutorials/qwen-image-2-1-gguf-comfyui/

**坑**：改 fork 时**备份目录不能留在 `custom_nodes/` 里** —— ComfyUI 会扫所有子目录，
备份也被当成节点加载（重复注册）。已挪到 `D:\ComfyUI\_backup\ComfyUI-GGUF.city96.bak`。

**实测**：换 fork 后 seed=42 输出与换前**完全一致**（2,015,356 字节）→ **GGUF 加载器不是审查问题的根源**。

## 环境
- conda env `comfyui`（Python 3.11.15），路径 `C:\Users\<PASSWORD>\miniconda3\envs\comfyui\python.exe`
- ComfyUI 0.37.0 装在 `D:\ComfyUI`，端口 **8188**，`--listen 0.0.0.0`
- 启动脚本 `D:\ComfyUI\_dl\start_comfy.ps1`；日志 `D:\ComfyUI\_dl\comfy.out` / `comfy.err`
- 出图 `D:\ComfyUI\output\`

## 排查顺序（下次直接照做）
1. `curl http://127.0.0.1:8188/system_stats` 看版本/GPU/VRAM
2. 报错先看 `comfy.err` 末尾 40 行的 Traceback
3. 模型没被识别 → `/object_info/<节点名>` 看列表
4. 形状不匹配 → 多半是文本编码器走了错分支，检查 state_dict key 格式