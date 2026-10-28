# Vision / 图片识别补全策略

当你的主模型不支持多模态（如 DeepSeek V4 Flash、LLaMA 等纯文本模型），在需要看图时可以通过以下方式补全。

## 如何检测模型是否支持 Vision

尝试使用 `vision_analyze` 工具分析一张图片。如果模型不支持，API 会返回：

```
Error code: 400 - unknown variant `image_url`, expected `text`
```

这表示模型只接受 text 类型的 content，不支持 image_url。

## 诊断当前配置

```bash
grep -A6 "auxiliary:\n  vision:" ~/.hermes/config.yaml
```

常见的失效原因是 `auxiliary.vision.provider: auto`，而主 provider 不支持视觉，auto fallback 也找不到后端。

## 方案对比

| 方案 | 成本 | 能看什么 | 配置复杂度 |
|------|------|---------|-----------|
| **1. 配置辅助视觉模型** | 按 API 使用量计费 | 图片全理解（照片、截图、图表） | 低 |
| **2. 本地 OCR（PaddleOCR）** | 免费，本地运行 | 仅文字识别（图片中的文字） | 中 |
| **3. 换主模型** | 取决于模型 | 图片全理解 | 低—中 |
| **4. 纯文本变通** | 免费 | 仅间接理解（通过工具获取文字信息） | 低 |

## 方案一：配置辅助视觉模型 ⭐ 推荐

在 `config.yaml` 中设置 `auxiliary.vision` 指向一个支持多模态的模型：

```yaml
auxiliary:
  vision:
    provider: openrouter          # 或 openai / google / anthropic
    model: openai/gpt-4o          # 支持视觉的模型
    api_key: sk-...               # 对应的 API Key
    timeout: 120
```

常用视觉模型：
- **OpenRouter:** `openai/gpt-4o`, `anthropic/claude-3.5-sonnet`, `google/gemini-2.0-flash`
- **OpenAI:** `gpt-4o` (需 `OPENAI_API_KEY`)
- **Google:** `gemini-2.0-flash` (需 `GOOGLE_API_KEY`)
- **Anthropic:** `claude-sonnet-4` (需 `ANTHROPIC_API_KEY`)
- **Moonshot/Kimi (月之暗面):** `kimi-k2.6` (需 Moonshot API Key)

### Moonshot/Kimi 特殊配置

如果 `provider: kimi` 在 auxiliary.vision 下报 401 认证错误，改用 `custom` 模式：

```bash
hermes config set auxiliary.vision.provider custom
hermes config set auxiliary.vision.model kimi-k2.6
hermes config set auxiliary.vision.base_url https://api.moonshot.cn/v1
hermes config set auxiliary.vision.api_key sk-...
hermes config set auxiliary.vision.api_key sk-...
hermes config set auxiliary.vision.timeout 120

⚠️ `hermes config set` 显示 Key 时会截断（如 `sk-by2...QZt3`），但实际文件里存的是完整值。可用 `grep api_key config.yaml` 验证长度以确认完整。

同时将 Key 写入 `.env`：
```bash
echo "KIMI_API_KEY=sk-..." >> ~/.hermes/.env
```

> **实测：** kimi-k2.6 通过 Moonshot API 能准确识别图片中的几何形状和颜色，对中文问答支持良好。
> 
> **验证方法：** 用 Pillow 创建一张简单测试图（几何形状），调用 `vision_analyze(image_url="/tmp/test.png", question="描述形状和颜色")`，返回详细描述即配置正确。

配置后，`vision_analyze` 工具会自动将图片发送给辅助模型分析，返回文字描述给主模型。对用户来说完全透明——我"看到"图片内容然后告诉你。

## 方案二：本地 OCR（免费，仅文字）

安装 PaddleOCR 提取图片中的文字：

```bash
pip install paddlepaddle paddleocr
```

使用方式：
```bash
python3 -c "from paddleocr import PaddleOCR; ocr = PaddleOCR(use_angle_cls=True); result = ocr.ocr('image.jpg'); print(result)"
```

优势：免费、离线、不消耗 API token
局限：只能识别文字，不能理解"这是什么猫"、"这张照片背景是哪里"

## 方案三：换主模型

直接换一个原生支持多模态的模型，一步到位：

```bash
hermes config set model.default gpt-4o
hermes config set model.provider openai
```

但通常更贵。适合经常看图的需求。

## 方案四：纯文本变通

某些场景可以不看图就获取信息：
- **网页截图？** → 用 `mcp_fetch_fetch` 或 Playwright 提取页面文字内容
- **Excel/PDF 图表？** → 用 `excel` MCP 或 OCR 工具读取数据
- **图片链接？** → 如果图片托管在网页上，先用 fetch 获取页面描述

这些方法虽然看不到图，但能获取到等价的文字信息。

## 最佳实践

1. **首选方案一** — 配置一个辅助视觉模型，让 `vision_analyze` 自动 fallback
2. 需要验真看照片、识别物体等场景，辅助模型是唯一可靠的方案
3. 如果只是偶尔需要认图片里的字，方案二（OCR）够用且免费
4. 辅助模型只在调用 `vision_analyze` 时才消耗 token，日常对话仍走便宜的主模型
