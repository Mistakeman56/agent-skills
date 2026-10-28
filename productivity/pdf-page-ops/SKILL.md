---
name: pdf-page-ops
description: "删/挑/合并 PDF 页面，并在交付前核验。用户要求删改 PDF 页时使用。"
trigger: "用户要求删/挑/合并 PDF 页面，或交付 PDF 前需要核验"
version: 1.0.0
metadata:
  hermes:
    category: productivity
    related_skills: [pdf, ocr-and-documents, invoice-forwarder]
---

# PDF 页级加工与交付前核验

对本地 PDF 做**页级**操作（挑页、删页、合并、重排、旋转），并在**发出去之前核验**。适用于发票合并件、考试/考纲文件、论文附件、扫描件等任何"改完要发给别人"的 PDF。

**核心纪律：先探测、再动手、必核验。** 交付件出错（删错页、漏页、内容没删干净）比不做更糟——用户是拿去报销/交差的。

## 第 0 步：先探测工具，不要凭记忆假设

**踩过的坑**：凭旧笔记直接用 `qpdf --pages`，结果本机根本没装，白写一条命令。**任何外部工具先 `command -v`，再规划路线。**

```bash
for c in pdftotext pdfinfo pdfseparate pdfunite pdftoppm pdfimages gs mutool qpdf pdftk libreoffice pandoc; do
  printf "%-12s %s\n" "$c" "$(command -v $c || echo '未安装')"
done
python3 -c "
import importlib
for m in ['pypdf','reportlab','pdfplumber','fitz','pypdfium2','pikepdf','PIL']:
    try: importlib.import_module(m); print(f'  {m:12} OK')
    except Exception: print(f'  {m:12} 未安装')"
```

- **poppler-utils 是保底方案**——它是最常见的一组 PDF 命令行工具，`pdfseparate`/`pdfunite` 就能完成全部挑页需求，一般不需要额外安装。
- 想要更省事的单条命令工具（`qpdf in.pdf --pages . 1,3-6 -- out.pdf`）而本机没有时，可装：`apt-get install -y qpdf`。
- 完整的实测工具清单见 `references/local-pdf-toolchain.md`（**带日期的快照，用前重新探测**）。

## 挑页 / 删页（最常用）

```bash
cd <工作目录>
rm -rf /tmp/pgsplit && mkdir -p /tmp/pgsplit

# 1) 拆成单页（p-1.pdf … p-N.pdf）
pdfseparate in.pdf /tmp/pgsplit/p-%d.pdf

# 2) 只把要保留的页按顺序合并（例：删掉第 2 页，保留 1,3,4,5,6）
pdfunite /tmp/pgsplit/p-1.pdf /tmp/pgsplit/p-3.pdf /tmp/pgsplit/p-4.pdf \
        /tmp/pgsplit/p-5.pdf /tmp/pgsplit/p-6.pdf out.pdf
```

**动手前先逐页读内容确认要删哪页**——别靠文件名或页序猜：

```bash
n=$(pdfinfo in.pdf | awk '/^Pages/{print $2}')
for i in $(seq 1 $n); do
  echo "----- PAGE $i -----"
  pdftotext -f $i -l $i -layout in.pdf - | grep -vE '^\s*$' | head -25
done
```

批量文件按某个字段分类时（如按"购方名称"分出公司抬头/个人抬头），用同一个循环把该字段打出来，**先分类再决定保留哪些页**：

```bash
for i in $(seq 1 $n); do
  echo -n "P$i: "
  pdftotext -f $i -l $i -layout in.pdf - | grep -oE '名 称[:：]\s*[^ ]+' | head -1
done
```

> 注意：不同开票系统排版不同，"名称"二字的空格数不一样，`grep` 可能漏掉某些页。**漏掉的页要单独再看一遍**，别当成"没有购方"。

## 交付前四项核验（缺一不可）

改完页之后**必须**跑完这四条再发，并在回复里把结果讲给用户听：

| # | 核验项 | 命令 | 通过标准 |
|---|---|---|---|
| 1 | 页数对 | `pdfinfo out.pdf \| grep Pages` | = 预期页数 |
| 2 | 内容真删干净 | `pdftotext -layout out.pdf - \| grep -c "<被删的标识>"` | **0** |
| 3 | 渲染健康 | `pdftoppm -png -r 50 out.pdf /tmp/chk && ls -la /tmp/chk*.png` | 每页都出 PNG 且体积正常 |
| 4 | 数值对得上 | `python3 -c "print(原合计-删掉的金额)"` | = 新文件里各页合计之和 |

第 1、2 条防"删错页/没删掉"，第 3 条防"结构损坏打不开"（页数为 0、PNG 为 0 字节都是坏了），第 4 条防"删错金额的那页"。

## 陷阱

- **`pdfseparate` 的 xref 警告不算失败**：它常打印 `Internal Error: xref num N not found but needed, document has changes, reconstruct aborted`，但**仍然正常输出每页**。不要因此重做或改用别的工具——用第 1/3 条核验裁决（页数对 + 能渲染出图 = 成功）。
- **输出文件名里带中文/空格一定加引号**，否则被 shell 拆词后报 `Couldn't open file '<乱码>'`。
- **核验一律针对最终合并件**，不要在 `pdfseparate` 的临时单页上做最终判断。
- **`pdfunite` 至少给两个输入**；保留页只有 1 页时直接用拆出来的单页当输出。
- **`pdftotext` 提取不到文本 ≠ 页面空白**：扫描件没有文本层。这种情况先 `pdftoppm` 出图再考虑 OCR（见 `ocr-and-documents` 技能），不要据此断言"这页是空的，可以删"。
- **改完不要覆盖原件**：新文件名体现差异（如 `..._新增5张_20260911.pdf`），原件留着以便用户反悔。

## 报告格式（assistant偏好）

结论先行 + 一张核验表 + 逐项列出保留下来的内容。他要看到"我逐项验过了"的证据，而不是一句"改好了"。

```
新文件：5 页  ¥1,000.72  ← 已删掉第 2 页（个人抬头 ¥155）

| 项 | 结果 |
|---|---|
| 页数 | 6 → 5 ✅ |
| "<被删标识>"出现次数 | 0 ✅ |
| 金额核对 | 696.61+97.81+… = 1000.72 = 1155.72−155.00 ✅ |
| 渲染检查 | 5 页全部正常出图 ✅ |
```

末尾用 `MEDIA:/绝对路径/文件.pdf` 交付（平台会当文档发出）。
