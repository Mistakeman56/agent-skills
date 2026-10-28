# VoiceBox — Open-Source AI Voice Studio

**Repo:** [jamiepine/voicebox](https://github.com/jamiepine/voicebox)
**Stars:** 25.9k | **Forks:** 3.1k | **Updated:** May 2026 (0.5.0)
**License:** MIT
**Stack:** Tauri (Rust) + Python backend

## What It Does

Voicebox is a **local-first AI voice studio** — a free open-source alternative to ElevenLabs and WisprFlow. Clone voices from seconds of audio, generate speech in 23 languages, dictate into any text field with a global hotkey, and give any MCP-aware AI agent a voice.

## Key Features

### Voice Cloning & TTS Engines (7 total)

| Engine | Languages | Strengths | VRAM |
|--------|-----------|-----------|:----:|
| **Qwen3-TTS** (0.6B/1.7B) | 10 | High-quality multilingual cloning, delivery instructions | ~2-4GB |
| **Qwen CustomVoice** | 10 | 9 preset voices, natural-language delivery control | ~2GB |
| **LuxTTS** | English only | Lightweight, 48kHz output, 150x realtime on CPU | ~1GB |
| **Chatterbox Multilingual** | 23🇺 | Broadest coverage (Arabic, Hindi, Swahili, etc.) | ~2GB |
| **Chatterbox Turbo** | English | Fast 350M model + paralinguistic tags ([laugh], [sigh]) | ~1GB |
| **TADA** (1B/3B) | 10 | HumeAI speech-language, 700s+ coherent audio | ~4-8GB |
| **Kokoro** | 8 | **82M model — CPU only!** 50 preset voices, fast inference | ✅ None |

### MCP Support

Voicebox has a **built-in MCP server** exposing tool `voicebox.speak`. Any MCP-aware agent (Claude Code, Cursor, Cline, **Hermes**) can call it to generate speech.

### Other Features

- Global dictation hotkey (push-to-talk + toggle modes)
- Post-processing: pitch shift, reverb, delay, chorus, compression, filters
- Unlimited generation length (auto-chunking with crossfade)
- Stories editor (multi-track timeline for conversations/podcasts)
- REST API for integrating into custom apps
- Voice personalities (attach persona to voice profile)
- Native Tauri performance (not Electron)
- Runs everywhere: macOS (MLX/Metal), Windows (CUDA), Linux (ROCm/Intel Arc/Docker)

## Installation Methods

### 1. Pre-built Binaries (macOS/Windows)

| Platform | URL |
|----------|-----|
| macOS Apple Silicon | https://voicebox.sh/download/mac-arm |
| macOS Intel | https://voicebox.sh/download/mac-intel |
| Windows | https://voicebox.sh/download/windows |

### 2. Docker

```bash
git clone https://github.com/jamiepine/voicebox.git
cd voicebox
docker compose up
# Runs on http://127.0.0.1:17493
```

### 3. Linux — Build from Source

No pre-built Linux binaries available yet. See [voicebox.sh/linux-install](https://voicebox.sh/linux-install) for instructions.

## Compatibility with Hermes (PVE LXC Environment)

**Known limitations (tested 2026-05-16):**

| Resource | Required | Available | Status |
|----------|:--------:|:---------:|:------:|
| Docker | ✅ | ❌ Not installed | ⚠️ Installable |
| GPU (CUDA) | ✅ Strongly recommended | ❌ No GPU (12700K iGPU, VT-x disabled) | ❌ |
| RAM | 8GB | 4GB total, ~2GB free | ❌ |
| Disk | ~30GB for models | ~70GB free | ✅ |

**Usable subset (CPU-only):**
- **Kokoro** (82M model): ✅ CPU inference, 8 languages, 50 preset voices, no cloning
- **LuxTTS**: ✅ Lightweight, English only, CPU inference
- Voice cloning: ❌ Requires GPU
- Qwen3-TTS/Chatterbox/TADA: ❌ Need GPU

**Recommendation:**
Full VoiceBox experience → install on **MacBook Air (Apple Silicon)** which has Neural Engine + Metal GPU acceleration. The MacBook can run all 7 engines including voice cloning.

Since the user prefers concise explanations and image-based sharing, and the current session explored this primarily as a comparison to gTTS, deeper integration with Hermes is **deferred** pending user interest and a suitable GPU-equipped host.

## Comparison: gTTS vs Edge TTS vs VoiceBox

| Feature | gTTS (current) | Edge TTS (default) | VoiceBox |
|---------|:--------------:|:------------------:|:--------:|
| Voice quality | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Chinese support | ✅ | ✅ | ✅ (Kokoro/Qwen) |
| Voice cloning | ❌ | ❌ | ✅ |
| Offline | ❌ | ❌ | ✅ |
| MCP integration | ❌ | ❌ | ✅ |
| Installation | pip install | Built-in | Docker/Desktop app |
| Network needed | translate.google.com | speech.platform.bing.com | None (local) |
| GPU needed | No | No | Recommended |
