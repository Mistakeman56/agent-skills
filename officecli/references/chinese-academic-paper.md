# Chinese Academic Paper Formatting with OfficeCLI

## Standard Format (本科毕业论文 / 课程设计)

### Page Setup (A4)
```bash
officecli set <file> /section[1] \
  --prop pageWidth=21cm --prop pageHeight=29.7cm \
  --prop marginTop=2.54cm --prop marginBottom=2.54cm \
  --prop marginLeft=3.17cm --prop marginRight=3.17cm
```

### Font Conventions (中国高校通用)
| Element | Font | Size | Bold | Notes |
|---------|------|------|------|-------|
| 论文标题 | 黑体 | 18pt (小二) | ✓ | 居中 |
| 作者/学院 | 宋体 | 10.5pt (五号) | ✗ | 居中 |
| "摘要" 标题 | 黑体 | 10.5pt (五号) | ✓ | 居中 |
| 摘要正文 | 宋体 | 10.5pt (五号) | ✗ | 两端对齐 |
| 关键词标签 | 黑体 | 10.5pt (五号) | ✓ | "关键词：" |
| 关键词内容 | 宋体 | 10.5pt (五号) | ✗ | 分号分隔 |
| 一级标题 (1 XX) | 黑体 | 14pt (四号) | ✓ | spaceBefore=12pt |
| 二级标题 (1.1 XX) | 黑体 | 12pt (小四) | ✓ | spaceBefore=6pt |
| 三级标题 (1.1.1 XX) | 黑体 | 12pt (小四) | ✓ | spaceBefore=6pt |
| 正文 | 宋体 | 12pt (小四) | ✗ | 两端对齐, lineSpacing=20pt |
| 页眉 | 宋体 | 9pt (小五) | ✗ | 居中 |
| 页脚/页码 | 宋体 | 9pt (小五) | ✗ | 居中 |
| 参考文献标题 | 黑体 | 14pt (四号) | ✓ | 居中 |
| 参考文献条目 | 宋体 | 10.5pt (五号) | ✗ | 两端对齐 |

### Header & Footer
```bash
# 页眉
officecli add <file> / --type header \
  --prop text="学校名" --prop align=center --prop font="宋体" --prop size=9

# 页脚（页码）
officecli add <file> / --type footer --prop field=page --prop align=center
```

### Section Hierarchy Template
```bash
# 一级标题
officecli add <file> /body --type paragraph \
  --prop text="1  绪论" --prop font="黑体" --prop size=14 --prop bold=true \
  --prop spaceBefore=12pt --prop spaceAfter=6pt

# 二级标题
officecli add <file> /body --type paragraph \
  --prop text="1.1  研究背景" --prop font="黑体" --prop size=12 --prop bold=true \
  --prop spaceBefore=6pt --prop spaceAfter=3pt

# 三级标题
officecli add <file> /body --type paragraph \
  --prop text="1.1.1  国内外现状" --prop font="黑体" --prop size=12 --prop bold=true \
  --prop spaceBefore=6pt --prop spaceAfter=3pt

# 正文
officecli add <file> /body --type paragraph \
  --prop text="正文内容..." --prop font="宋体" --prop size=12 \
  --prop align=justify --prop lineSpacing=20pt --prop lineRule=exact
```

### Three-Line Table (三线表)
```bash
# 创建表格
officecli add <file> /body --type table --prop rows=4 --prop cols=3

# 表头（加粗居中）
officecli set <file> '/body/tbl[1]/tr[1]/tc[1]' --prop text="列1" --prop bold=true --prop align=center

# 数据行
officecli set <file> '/body/tbl[1]/tr[2]/tc[1]' --prop text="数据"
```
注意：默认表格有完整边框。三线表需要通过 raw-set 修改边框样式（顶线/底线1.5pt，中间线0.5pt，无竖线），或在 Word/WPS 中手动调整。

### East Asian Font Slot (中西文字体分离)
```bash
# 设置中文正文（宋体）但英文 Times New Roman
officecli set <file> '/body/p[N]/r[1]' \
  --prop font="宋体" --prop font.ea="宋体" --prop font.latin="Times New Roman"

# style 级别设置
officecli add <file> /styles --type style --prop id=BodyCN \
  --prop font="Times New Roman" --prop font.ea="宋体" --prop size=12
```

## Embedding Diagrams (架构图/流程图)

When the paper needs architecture diagrams or flowcharts:
1. Generate HTML with `architecture-diagram` skill (dark-themed SVG)
2. Convert to PNG via Playwright: `page.screenshot(path='diagram.png', full_page=True)`
3. Insert into docx with python-docx: `doc.add_picture('diagram.png', width=Inches(6.0))`
4. Add caption below: `doc.add_paragraph('图1 系统架构图').alignment = WD_ALIGN_PARAGRAPH.CENTER`

**User preference:** assistant要求论文"图文并茂"，不能只有纯文字。至少放2-3张图（架构图、流程图、实际截图）。纯理论综述会被说"太干巴了"——必须结合真实项目经验、实际部署截图、交互对话截图。优先写实践经验，理论综述为辅。

**User preference on accuracy:** 永远不要猜测/编造硬件配置、系统参数等技术细节。必须SSH到实际服务器查询精确数据（`lscpu`, `free -h`, `pct config`等）。用户会明确纠正错误的规格信息。

**WeChat file sending:** `send_message` 工具发送文件时容易触发iLink限速。多次发送需间隔10秒以上。如果持续限速，直接提供文件路径让用户自行获取。

## Pitfalls

1. **`-o` flag on `view html`** — `officecli view file.docx html -o out.html` 输出到 stdout 而非文件。用重定向：`officecli view file.docx html > out.html`

2. **Linux 中文字体渲染** — HTML 预览中黑体/宋体回退为系统默认字体，但 **docx 文件本身保存了正确的字体引用**，在 Windows/Mac 的 Word 中打开显示正确。

3. **首行缩进** — 用 `--prop firstLineIndent=2em` 或 `--prop firstLineIndent=480` (2字符×240 twips/字符)

4. **Shell 中括号** — 路径中的 `[N]` 必须加引号：`'/body/p[1]'`，否则 bash 会 glob 展开

5. **`lineRule` 配合 `lineSpacing`** — 固定行距用 `--prop lineSpacing=20pt --prop lineRule=exact`，倍数行距用 `--prop lineSpacing=1.5 --prop lineRule=auto`

6. **交付论文前必须对照作业要求验证结构** — 写完/改完论文后，先读一遍实际的作业要求文档（用户发的评分标准文件），逐条比对：章节结构是否匹配模板、内容方向是否符合题意、格式是否达标。不要假设结构正确就直接交付。曾因没对照要求就交付，导致7章结构完全对不上模板要求的"概述→方法→展望→结论"四章结构，整个主体内容需要重写。**验证步骤：读要求 → 列checklist → 逐项对比 → 修复后再交付。**

7. **旧 .doc 文件读取用 antiword** — `officecli` 不支持 `.doc`（旧格式），`libreoffice --headless --convert-to docx` 在部分文件上也会失败。最可靠方案：`apt-get install -y antiword && antiword file.doc`。如需保留格式，先 LibreOffice 转换再 officecli 处理。

8. **参考文献不能凑数** — 删除产品公告（ChatGPT博客、Claude Model Card）、GitHub项目链接（GPT-Engineer、AutoGPT）、重复引用、水分论文。保留有学术含量的论文/综述/会议论文。42篇已远超20篇要求，质量>数量。用户原话："参考文献有点过于凑数了，就是chatgpt那种都算，我觉得还是删掉吧"

9. **课程论文框架技巧** — 当用户有实际项目经验时，最佳框架是"通过部署X来研究Y技术"，每个技术方向都是"文献演进+实践验证"的双线结构。不要写成纯项目报告，也不要写成纯理论综述。用户原话："我们可不可以就是写成通过部署Hermes去研究什么东西，这样是不是不跑题了？"

10. **作业要求文档丢失时的恢复流程** — 用户隔天回来问"论文跑题没"时，评分标准文件可能已不在磁盘（临时文件被清理）。恢复步骤：① `session_search(query="评分标准 考察要求 大作业")` 找到之前讨论要求的会话 → ② 从会话摘要中提取结构要求（如"概述→方法→展望→结论"四章模板） → ③ 用 `python-docx` 快速审计论文结构：`doc = Document('file.docx'); [print(f'[{i}] ({p.style.name}) {p.text[:100]}') for i, p in enumerate(doc.paragraphs) if p.text.strip()]` → ④ 对照要求逐章比对，输出结论。这个流程比重新找文档快得多，且 `session_search` 的摘要通常保留了足够的要求细节。

11. **python-docx 快速结构审计** — 不需要 officecli，直接 python3 即可提取段落样式名+文本前100字。用于快速判断：章节标题是否匹配模板、是否有摘要/关键词、参考文献是否存在等。比 officecli view outline 更灵活（可自定义过滤条件）。

12. **学术诚信：绝不夸大用户贡献** — 用户部署/配置/研究了开源项目≠开发了该项目。论文中写开源项目必须明确标注出处（GitHub链接+作者/组织），用户角色="部署+配置+实践验证"。常见错误表述→正确表述：~~"笔者独立构建的系统"~~ → "由X开发的开源项目，笔者对其进行了部署和配置"；~~"在开发过程中"~~ → "在部署和使用过程中"；~~"笔者采用了XX方法"~~ → "开源社区通过XX方式迭代"。**这是红线，触犯会导致用户强烈不满。**

13. **技术细节必须准确** — 模型名称、版本号、API接口等必须与用户实际使用的一致，不能用泛化的例子代替。写之前先问用户实际用的是什么，不要假设。

14. **论文内容需多轮校对** — 用户会在每轮审查中发现新的问题（夸大、不准确、凑数）。不要期望一次写完就完美。流程：初稿→用户审查→修正→再审查→再修正→最终版。每轮修正后全文扫描，不留遗漏。

15. **python-docx 引用编号替换必须按 run 级别操作** — python-docx 中，"[N]"引用编号通常在独立的 run 中（如 run[0]="MemGPT"，run[1]="[7]"），简单字符串替换 `p.text.replace("[7]","[12]")` 不会生效。正确做法：遍历每个 run，用上下文判断（前一个 run 的文本）决定替换哪个编号。代码示例：
```python
for i, run in enumerate(p.runs):
    if re.match(r'^\[\d+\]$', run.text.strip()):
        prev_text = p.runs[i-1].text[-40:] if i > 0 else ''
        if 'MemGPT' in prev_text:
            run.text = '[12]'  # MemGPT 的正确编号
```

16. **批量修改后必须全文验证，不能只验证部分** — 改了引用编号后，必须检查：①所有正文引用是否都有对应参考文献 ②所有参考文献是否都被引用 ③有没有孤立引用。遗漏检查会导致交付后用户发现问题再返工。

17. **图片占位符必须是独立段落** — 不能用 `run.text += '占位符'` 追加到现有段落（用户看不到或混在正文里）。必须用 lxml 操作 XML 创建独立段落并 `addnext` 到锚点段落后。居中加粗灰色。

18. **图表标题格式必须全文统一** — 所有"图N"和"表N"标题必须：相同字号（五号=10.5pt）、相同字体（中文宋体/英文Times New Roman）、相同加粗、相同对齐（居中）。用代码批量设置，不能手动逐个改。

19. **过度编辑是最大陷阱** — 每次修改都可能引入新问题。最佳策略：①一次改一类问题 ②改完立即验证 ③验证通过再改下一类。不要同时改引用+格式+内容。用户原话："你能不能好好看看，把所有错误引用或空参考文献都整理出来"——说明前几轮修改引入了新的遗漏。

20. **用户偏好"列清单自己改"而非"我直接改"** — 当修改涉及大量分散的引用编号时，用户更倾向于我输出一份清晰的修改清单（搜什么关键词、改成什么），由用户手动在Word中执行。原因是python-docx自动化修改容易引入格式破坏（font丢失、run合并、样式覆盖），用户觉得"你一改就全乱了"。判断标准：修改<5处且在同一段落→直接改没问题；修改>10处且分散全文→先输出清单让用户确认。用户原话："不是咋改啊...你告诉我都改哪块，我手动修改"

21. **引用编号错误排查的子代理并行策略** — 全文审计引用编号时，用delegate_task开两个子代理：一个做代码分析（提取所有引用+参考文献交叉验证），一个做视觉检查（转PDF逐页审阅）。代码分析快但可能遗漏格式问题，视觉检查慢但能发现渲染层面的问题。两个结果汇总后给用户完整清单。用户原话："你让子代理来一起找，看图片找，代码找，反正好好找"

22. **参考文献编号重排后的连锁反应** — 删减/重排参考文献列表后，正文中的引用编号必须全部更新。常见遗漏：摘要中的引用、图表标题中的引用、跨run的引用（python-docx中[N]在独立run里）。最危险的错误是正文引用了已删除的编号（如引用[7]但[7]已被删除）。必须在每次重排后做全文交叉验证。

23. **"修好了"≠真的修好了** — 每次声称修复了引用/格式问题后，必须重新扫描验证，不能凭第一轮修改就报告成功。python-docx的run级替换非常容易漏掉（跨run的引用、隐藏段落中的引用、表格中的引用）。用户原话：\"你能不能好好看看，把所有错误引用或空参考文献都整理出来\"。**规则：改完→重新全文扫描→确认0错误→再报告。**

24. **引用编号修正后必须区分"该删"和"该改"** — 不是所有错误引用都应该改成另一个编号。有些引用指向的论文根本不在参考文献列表里（如DeepSeek的引用），这类应该**直接删除引用号**而非改成错误的编号。判断方法：先列出所有参考文献的论文名→逐个检查正文引用→如果引用的论文不在列表里→删引用号。

25. **用户自行修改Word后需重新审计** — 用户在Word中手动修改格式/内容后，python-docx读到的可能是全新状态。不要假设上次的修改还在。每次用户提供新版本的docx，都必须重新完整审计，不能基于旧版本的记忆。

26. **图片占位符不要放在封面** — python-docx的`insert_paragraph_after`操作可能把新段落插到错误位置（如封面区域）。插入占位符后必须验证：①占位符在正确的章节位置 ②封面页没有多余内容 ③占位符是独立段落（不是追加到现有段落里）。

27. **图表标题格式不一致是高频投诉** — 用户特别在意图表标题的视觉一致性。所有图/表标题必须：五号(10.5pt)、加粗、居中、中文字体/英文Times New Roman。不能有的有英文标题有的没有，不能有的居中有的不居中。**用代码批量设置，不能逐个手改。**
