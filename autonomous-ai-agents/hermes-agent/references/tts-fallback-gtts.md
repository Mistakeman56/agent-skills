# TTS Fallback: gTTS (Google Text-to-Speech)

When the configured TTS provider (`edge`) fails, **gTTS** (Google Text-to-Speech) serves as a reliable zero-config fallback on Linux.

## Trigger

`text_to_speech` tool returns:
```
TTS generation failed (edge): Cannot connect to host speech.platform.bing.com:443
ssl:<ssl.SSLContext object at 0x...> [None]
```

Root cause: The server's outbound HTTPS connection to Microsoft's Bing speech endpoint is blocked (no internet routing, firewall, or DNS issue specific to `speech.platform.bing.com`). The server CAN reach other sites (baidu.com returns 200), so this is not a general network outage.

## Resolution — Use gTTS Directly

### Install

```bash
pip install --break-system-packages gTTS
```

### Generate & Save

```python
from gtts import gTTS
tts = gTTS('你的文本内容', lang='zh-cn')
tts.save('/tmp/hermes_voice.mp3')
# File is MP3 format, typically ~30KB for 10s of speech
```

### Send via MEDIA Tag

Include in your response:
```
MEDIA:/tmp/hermes_voice.mp3
```

This sends the file natively as a playable voice message on WeChat/Weixin.

### Proxy Consideration

- On this server, gTTS works **without** a proxy — the Google Translate API endpoint (`translate.google.com`) is reachable directly
- If behind a corporate firewall that blocks Google, route through the Clash proxy with auth:
  ```bash
  HTTP_PROXY=http://Clash:hrFM183F@192.0.2.10:7890 \
  HTTPS_PROXY=http://Clash:hrFM183F@192.0.2.10:7890 \
  python3 -c "from gtts import gTTS; gTTS('test', lang='zh-cn').save('/tmp/t.mp3')"
  ```

## Known Limitations

| Aspect | Detail |
|--------|--------|
| **Network required** | gTTS is an online API (Google Translate TTS backend). No offline mode. |
| **Voice quality** | Single voice per language; no emotion/expressiveness control. Sounds like standard Google Translate voice. |
| **Language** | `lang='zh-cn'` for Mandarin Chinese, `lang='en'` for English |
| **Rate limiting** | No hard limit observed, but Google may throttle at very high volume (>1000 requests/hour) |
| **File format** | Always saves as MP3 |
| **Speed** | ~2-3 seconds for a 15-second clip |

## Comparison with Configured Providers

| Provider | Status on this server | Requires API key? |
|----------|----------------------|-------------------|
| Edge TTS (default) | ❌ Fails — SSL blocked | No |
| gTTS (manual fallback) | ✅ Works | No |
| OpenAI TTS | ❌ No API key configured | Yes (`VOICE_TOOLS_OPENAI_KEY`) |
| ElevenLabs | ❌ No API key configured | Yes (`ELEVENLABS_API_KEY`) |
| Piper TTS (local) | ⚠️ Not installed | No |

## When to Use gTTS vs Fix Edge TTS

- **If the user just wants a quick voice message** → use gTTS (works now, no config changes)
- **If voice quality matters** (emotional/professional) → configure a paid provider like ElevenLabs or OpenAI TTS with their API key
- **To fix Edge TTS** → needs outbound HTTPS to `speech.platform.bing.com` — either route through proxy or fix server firewall rules. Not a Hermes config issue.

## Text-to-Image for WeChat Forwarding

When the user wants to forward formatted content (Markdown tables, styled text) from WeChat to others and plain text forwarding loses formatting:

**Approach (discussed but not yet implemented):**
1. Render the content as a styled HTML page (inline CSS, readable font sizes, matching WeChat color scheme)
2. Use the browser tool to open the HTML file
3. Screenshot the rendered page
4. Send the screenshot image via `MEDIA:` path

Token cost estimate: ~100 tokens for HTML generation + ~0 for browser screenshot (no LLM involved in capture step) = negligible.
