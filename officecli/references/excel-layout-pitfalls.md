# Excel Layout Pitfalls (openpyxl)

## Text-heavy cells need generous row heights

When `wrap_text=True` is set, openpyxl does NOT auto-size rows. The default row height (~15pt) only shows 1-2 lines. Long paragraphs appear cramped/clumped.

**Fix**: Set `ws.row_dimensions[r].height` explicitly. Rule of thumb:
- 1-2 lines of text: 25-30pt
- 3-5 lines: 50-80pt
- 6+ lines (financial analysis paragraphs): 100-160pt
- Table headers: 28-32pt
- Data rows: 16-20pt

## Column widths must fit longest content

A=20 is too narrow for Chinese text like "集团工资及社保公积金". 
- Text columns (A, B, F): 24-30 width
- Number columns (C, D, E): 16-22 width

## Merged cells: set values BEFORE merging

openpyxl raises `AttributeError: 'MergedCell' object attribute 'value' is read-only` if you try to write to a cell that's already part of a merged range.

**Pattern**: Write all cell values first, THEN call `ws.merge_cells()`. Never merge before writing.

## Number format by column, not global

Chinese financial templates use different formats per column:
- **Plan/Actual columns**: `General` format (no commas, no decimals forced)
- **Difference columns**: `#,##0.00_);[Red](#,##0.00)` (red parentheses for negatives)
- **Pie chart percentages**: `0.00%`
- **Total/subtotal rows**: Red format even for plan/actual columns

Applying one format globally looks wrong.

## Borders on ALL cells

Templates almost always have thin borders on every cell. Missing borders makes output look unfinished. Apply after all data is written:
```python
for r in range(1, max_row+1):
    for c in range(1, max_col+1):
        ws.cell(row=r, column=c).border = thin_border
```

## Alignment matters

- Text: `Alignment(wrap_text=True, vertical='top', horizontal='left')`
- Numbers: `Alignment(vertical='top', horizontal='right')` for difference columns
- Headers: `Alignment(wrap_text=True, vertical='center', horizontal='center')`
- The template's alignment (left vs right for numbers) must match exactly

## Visual verification is mandatory

After generating Excel, ALWAYS take a screenshot and visually inspect:
```bash
officecli view file.xlsx screenshot -o /tmp/check.png
```
Compare with the source template. Common missed issues: text cramped, numbers in wrong columns, missing borders, wrong font.
