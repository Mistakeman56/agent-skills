# 本地 PDF 工具链实测快照

> **快照日期：2026-09-11**（Hermes 主机，Linux）。环境会变，**用前务必按 SKILL.md 第 0 步重新探测**，不要拿这份清单当既定事实。
> "未命中"只表示当次不在 PATH 上，不代表不可用——记下安装命令即可。

## 探测命令

```bash
for c in pdftotext pdfinfo pdfseparate pdfunite pdftoppm pdfimages pdftocairo gs mutool qpdf pdftk pdfcpu libreoffice soffice magick convert pandoc tesseract ocrmypdf; do
  printf "%-12s %s\n" "$c" "$(command -v $c || echo '未安装')"
done
python3 -c "
import importlib
for m in ['pypdf','reportlab','pdfplumber','fitz','pypdfium2','pikepdf','pdf2image','PIL']:
    try: importlib.import_module(m); print(f'  {m:12} OK')
    except Exception: print(f'  {m:12} 未安装')"
```

## 2026-09-11 实测结果

**可用（已实测过功能）**

| 工具 | 版本 | 本次验证过的用途 |
|---|---|---|
| `pdftotext` | poppler-utils 22.12.0 | 逐页提取文本（`-f N -l N -layout`）——核对发票购方/金额靠它 |
| `pdfinfo` | 22.12.0 | 页数、页尺寸、是否加密 |
| `pdfseparate` | 22.12.0 | PDF → 单页系列 ✅ |
| `pdfunite` | 22.12.0 | 多页/多文件合并 ✅ |
| `pdftoppm` | 22.12.0 | PDF → PNG（`-png -r 50`）渲染健康检查 ✅ |

**存在但本次未深测**：`pdfimages`、`pdftocairo`（同属 poppler）、`gs`（Ghostscript）、`mutool`（MuPDF）、`libreoffice`/`soffice`、`pandoc`。

**Python 库**：`pdfplumber` 0.11.10 ✅（提表格/精细读文本）、`PyMuPDF`(fitz) 1.28.0 ✅（页面操作、渲染）、`pypdfium2` ✅、`PIL` 12.2.0 ✅。

**当次未命中 → 用前装**

| 工具 | 安装 | 装它的理由 |
|---|---|---|
| `qpdf` | `apt-get install -y qpdf` | 单条命令挑页最省事：`qpdf in.pdf --pages . 1,3-6 -- out.pdf` |
| `pdftk` | `apt-get install -y pdftk-java` | 老牌旋转/重排 |
| `pdfcpu` | `apt-get install -y pdfcpu` | Go 写的批处理 |
| ImageMagick (`convert`/`magick`) | `apt-get install -y imagemagick` | 图像层加工（**注意：PDF 相关策略在部分发行版默认被禁**） |
| `tesseract` / `ocrmypdf` | `apt-get install -y tesseract-ocr ocrmypdf` | 扫描件 OCR（见 `ocr-and-documents` 技能） |
| `pypdf` / `reportlab` | `pip install pypdf reportlab` | 写"创建 PDF / 填表单"类脚本（bundled `pdf` 技能的脚本依赖它俩） |
| `pikepdf` | `pip install pikepdf` | 底层对象级修补 |

## 能力 → 命令速查

| 想干的事 | 保底命令（poppler，无需安装） |
|---|---|
| 看有几页 | `pdfinfo f.pdf \| grep Pages` |
| 逐页读文字 | `pdftotext -f 2 -l 2 -layout f.pdf -` |
| 读全文 | `pdftotext -layout f.pdf -` |
| 拆成单页 | `pdfseparate f.pdf /tmp/p/p-%d.pdf` |
| 合并/挑页 | `pdfunite p-1.pdf p-3.pdf out.pdf` |
| 页 → 图 | `pdftoppm -png -r 50 f.pdf /tmp/chk` |
| 抽内嵌图片 | `pdfimages -list f.pdf` / `pdfimages -png f.pdf /tmp/img` |

旋转、重排、压缩、加密、表单填充等更"重"的需求：`qpdf`/`mutool`/`gs`，或者 Python `pypdf`（bundled `pdf` 技能的 `scripts/pdf_*.py` 就是干这些的，依赖未装时按上表 pip 一下）。

## 实战案例：发票合并件删掉"个人抬头"那页

**背景**：交付给assistant的发票合并件 `发票汇总_新增6张_20260911.pdf`（6 页，¥1,155.72），其中第 2 页购方是**他本人姓名（个人抬头，¥155）**，他要求删掉该页再发（公司抬头才能报销）。

**定位**：逐页读文本 → 命中第 2 页（个人姓名 + ¥155 + 商品为床垫）。

**执行**：

```bash
cd ~/.hermes/office-docs
rm -rf /tmp/pgsplit && mkdir -p /tmp/pgsplit
pdfseparate 发票汇总_新增6张_20260911.pdf /tmp/pgsplit/p-%d.pdf
pdfunite /tmp/pgsplit/p-1.pdf /tmp/pgsplit/p-3.pdf /tmp/pgsplit/p-4.pdf \
         /tmp/pgsplit/p-5.pdf /tmp/pgsplit/p-6.pdf 发票汇总_新增5张_20260911.pdf
```

`pdfseparate` 打了两条 `Internal Error: xref num ... reconstruct aborted` 警告，**但 6 个单页全部正常生成**——按 SKILL.md 的核验裁决，忽略警告、以核验结果为准。

**四项核验实际输出**：

| 项 | 结果 |
|---|---|
| `pdfinfo` 页数 | `Pages: 5` ✅（原 6） |
| `pdftotext -layout … \| grep -c "user"` | `0` ✅（原为 1） |
| `pdftoppm -png -r 50` 出图 | 5 张 PNG，24–29KB 各一 ✅ |
| 金额 | 696.61+97.81+69.00+54.30+83.00 = **1000.72** = 1155.72 − 155.00 ✅ |
| 逐页购方复核 | 全部 = 某公司 ✅（注：首/末页排版空格不同，`grep '名 称[:：]'` 会漏，需单独确认） |

**交付**：`MEDIA:~/.hermes/office-docs/发票汇总_新增5张_20260911.pdf`

## 业务注记：发票购方分两类

- **公司抬头**：某公司（纳税人识别号 `<TAX_ID>`）→ 报销用，**默认全发**
- **个人抬头**：assistant本人姓名 → 与公司报销无关，**公司件里原则上剔除**（详见 `invoice-forwarder` 技能）

交付前先逐页分类，能省掉"发完再删重发"这一轮。
