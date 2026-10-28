---
name: stirling-pdf
description: "Use when OCR、压缩、转换或归档 PDF。"
trigger: "OCR 扫描件、PDF 压缩/转换、把文档存进 Stirling 文件库"
---

# Stirling-PDF 运维与使用

## 部署位置

- **PVE CT <ID>**，`192.0.2.10:8080`，内网直连
- **公网域名**：`https://pdf.example.com:18443`（也支持 443），Caddy 反代
- 账号存 `.env`：`STIRLING_USER` / `STIRLING_PASSWORD`
- CT 配置：2核 / 4G / 20G，容器内存上限 3g
- 数据目录 `/opt/stirling/`：configs、logs、customFiles、pipeline、tessdata

## 改密码（易错）

**必须用 `change-password-on-login`，不是 `change-password`**。前者会同时清 firstLogin 标记，后者只改密码 → 登录后陷入「反复要求首次登录改密」的死循环。

**密码至少 8 位**。低于 8 位系统会一遍遍要求改，表现就是弹窗关不掉。

```bash
TOK=$(curl -s -X POST "$S/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"username\":\"admin\",\"password\":\"<old>\"}" | jq -r .session.access_token)
curl -X POST "$S/api/v1/user/change-password-on-login?currentPassword=<old>&newPassword=<new>&confirmPassword=<new>" \
  -H "Authorization: Bearer $TOK"
# 验证（必须 false）
curl -s "$S/api/v1/proprietary/ui-data/login" | jq .firstTimeSetup
```

API 路径是 `/api/v1/auth/login`，**不是** `/api/v1/user/login`（那个返回 401）。

## 中文 OCR（踩坑最多，照抄）

```bash
curl -X POST "$S/api/v1/misc/ocr-pdf" -H "Authorization: Bearer $TOK" \
  -F "fileInput=@in.pdf" -F "languages=chi_sim" \
  -F "ocrType=skip-text" -F "ocrRenderType=sandwich" \
  -F "deskew=true" -F "clean=true" -o out.pdf
```

**四个必踩的坑：**

1. **不要把空目录挂载到 `/usr/share/tesseract-ocr/5/tessdata`**。空挂载会遮住镜像自带的 `chi_sim.traineddata`、`configs/`（25 个配置）、`pdf.ttf`，Tesseract 报 `TesseractConfigError: Error occurred while parsing a Tesseract configuration file`。要自定义就先把镜像里的整体提取出来：
   ```bash
   CID=$(docker create <image>)
   docker cp $CID:/usr/share/tesseract-ocr/5/tessdata/. /opt/stirling/tessdata/
   docker rm $CID
   ```
   替换目录后**必须 `docker restart`**，否则挂载仍指向旧 inode。
2. **`tessdata_best` 不兼容** ocrmypdf 17.x，报 exit code 9。用镜像自带的或 `tessdata_fast`。
3. **`ocrRenderType` 只接受 `hocr` / `sandwich`**。ocrmypdf 17.13 已移除 hocr 渲染器，但默认值还是 hocr → 必传 `sandwich`。传 `pdf`/`textonly`/`auto` 一律 400。
4. **OCR 输出的汉字之间有空格**，`全面深化改革` 变成 `全面 深化 改革`，关键词搜不到。必须做后处理（见 `scripts/ocr_clean_text.py`）合并相邻 CJK 字符间的空白。

**性能**：约 2.1 s/页；高分辨率扫描件（如 65M/93页）会到 3.8 s/页。273 页约 10 分钟。

## 文件库（Storage）API

```
POST  /api/v1/auth/login              {"username":..,"password":..} → session.access_token
POST  /api/v1/storage/folders         {"name":"发票","parentFolderId":null} → id
POST  /api/v1/storage/files           multipart，字段名必须叫 file（没有 folderId 参数）→ id
PATCH /api/v1/storage/files/folder    {"fileIds":[..],"folderId":"<uuid>"}；folderId 传 null 移出
```

上传后要单独 PATCH 才能放进文件夹。

## 其他能力速查

- `analysis/*`：页数、字体、表单域、页尺寸、安全信息
- `misc/*`：压缩、合并、拆页、加页码、提取图片、修复、去密码、加附件
- `convert/*`：PDF↔Word/Excel/图片/HTML/Markdown/EPUB，还有 **cbr/cbz→pdf**（漫画）、**eml→pdf**（邮件存档）
- `security/*`：`auto-redact`（真删除敏感信息）、`sanitize-pdf`（去内嵌脚本）、`cert-sign`（证书签名、多方会签）
- `filter/*`：按大小/页数/是否含图/是否含文字筛选——接 pipeline 做条件分支
- `processing-folders` / `/pipeline/watchedFolders`：丢文件进目录自动处理，每分钟扫一次
- `docparse/ingest`：向量化入知识库，**需外接 embedding 引擎**，默认 `engineReachable=false`

## 发票归档流水线（已启用）

`~/.hermes/scripts/invoice_archive.py` + `invoice-archive.timer`，每 30 分钟在 `:15`/`:45` 跑，把 `office-docs/*.pdf` 里的发票上传到「发票」文件夹，纯脚本 0 token。幂等记录在 `state/invoice_archived.json`。详见 `invoice-forwarder` 技能。
