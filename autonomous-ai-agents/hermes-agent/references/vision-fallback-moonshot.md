# Moonshot Kimi k2.6 Vision Fallback Setup

当主模型不支持视觉（如 deepseek-v4-flash），配置 Moonshot Kimi 2.6 作为辅助视觉模型。

## 配置步骤

### 1. 添加 API Key 到 .env
```bash
echo "KIMI_API_KEY=sk-xxxx..." >> ~/.hermes/.env
```

### 2. 配置 auxiliary.vision（必须用 provider: custom）
```bash
hermes config set auxiliary.vision.provider custom
hermes config set auxiliary.vision.model kimi-k2.6
hermes config set auxiliary.vision.base_url https://api.moonshot.cn/v1
hermes config set auxiliary.vision.timeout 120
```

**不要用 `provider: kimi`** — Kimi 原生 provider 在 auxiliary 中会 401，必须用 `provider: custom` 并显式指定 `base_url` 和 `api_key`。

### 3. 在 config.yaml 中填入 api_key
`hermes config set` 会在终端显示截断（如 `sk-xxx...zzz`），但实际写入完整。可用 sed 或 Python 确认：
```bash
python3 -c "
with open('~/.hermes/config.yaml') as f:
    for i, line in enumerate(f):
        if 'vision:' in line:
            for j in range(i, i+8):
                print(lines[j])
"
```

### 4. 测试
```bash
vision_analyze(image_url="/path/to/image.png", question="描述这张图")
```

预期返回详细的形状、颜色描述。

## Token 开销
- 仅当 `vision_analyze` 被调用时激活
- 日常聊天仍用主模型（如 deepseek-v4-flash），零额外消耗
- 每张图约 50-300 token（取决于图像复杂度）

## 已知问题
- `provider: kimi` 在 auxiliary 中不可用（401 Invalid Authentication）
- `provider: custom` 是唯一可行方案
- Key 明文存储在 config.yaml 中（和主 model 的 DeepSeek Key 同模式）
