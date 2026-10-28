#!/usr/bin/env python3
"""用 Kimi (Moonshot) 视觉 API 分析图片 — 主模型无视觉时的兜底路径。

用法:
    ~/.hermes/hermes-agent/venv/bin/python analyze_image_kimi.py <图片路径> "<问题>"

依赖: openai SDK（hermes venv 自带），KIMI_API_KEY 在 ~/.hermes/.env
2026-08 实测: 模型 moonshot-v1-8k-vision-preview 可分析人物/场景/图内文字
"""
import os
import sys
import base64
from openai import OpenAI


def load_env(path='~/.hermes/.env'):
    for line in open(path):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k, v)


def main():
    if len(sys.argv) < 3:
        print('用法: analyze_image_kimi.py <图片路径> "<问题>"')
        sys.exit(1)
    img_path, question = sys.argv[1], sys.argv[2]
    load_env()
    img = base64.b64encode(open(img_path, 'rb').read()).decode()
    client = OpenAI(api_key=os.environ['KIMI_API_KEY'],
                    base_url='https://api.moonshot.cn/v1')
    resp = client.chat.completions.create(
        model='moonshot-v1-8k-vision-preview',
        messages=[{'role': 'user', 'content': [
            {'type': 'text', 'text': question},
            {'type': 'image_url',
             'image_url': {'url': f'data:image/jpeg;base64,{img}'}}
        ]}],
        max_tokens=600
    )
    print(resp.choices[0].message.content)


if __name__ == '__main__':
    main()
