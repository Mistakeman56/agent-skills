# Excel Template Matching Workflow

When creating an Excel file to match an existing template, extract ALL formatting properties first before writing data.

## Step-by-step

1. **Read the template** with `xlrd` (for .xls) or `openpyxl` (for .xlsx) with `formatting_info=True`
2. **Extract these properties** from the template:
   - **Font**: name, size, bold, italic, colour_index for every non-empty cell
   - **Number format**: `xf.format_key` → `format_map[key].format_str` — note `General` vs `#,##0.00_);[Red](#,##0.00)` etc.
   - **Alignment**: `hor_align` (0=left, 1=center, 2=right, 3=general), `ver_align`, `text_wrapped`
   - **Borders**: line style on all four sides
   - **Column widths**: `colinfo_map` (width in 1/256th of character)
   - **Row heights**: `rowinfo_map` (height in 1/20th of point)
   - **Merged cells**: `ws.merged_cells` list
3. **Write data** with matching properties in this order:
   - Set ALL cell values first (no merges yet)
   - Add borders to all cells
   - Merge cells LAST (merge clears values on non-anchor cells)
4. **Verify** with `officecli view <file> screenshot`

## Common pitfalls

- **openpyxl merge order**: You MUST set cell values BEFORE calling `merge_cells()`. Merging after setting values on the anchor cell works; setting values on already-merged cells throws `AttributementError: 'MergedCell' object attribute 'value' is read-only`.
- **Number format for financial templates**: Difference/variance columns typically use `#,##0.00_);[Red](#,##0.00)` (negative in red with parentheses). Plan/actual columns often use `General`.
- **Row heights for long text**: Merged cells with wrap_text need generous row heights — default 15pt is way too small for paragraphs. Set to 55-160pt depending on text length.
- **Column widths**: Chinese text needs wider columns (A=20-28 chars for text-heavy columns).
- **Font consistency**: Chinese financial templates almost always use 仿宋 (FangSong), not 宋体 (SimSun). Title 16pt bold, body 10pt bold.
