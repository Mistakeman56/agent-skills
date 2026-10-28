# xlrd format inspection script for .xls templates
# Usage: python3 xls-format-inspection.py <template.xls>
# Extracts font, number format, alignment, borders, and merged cells from every cell.

import xlrd
import sys

def inspect(path):
    wb = xlrd.open_workbook(path, formatting_info=True)
    for sn in wb.sheet_names():
        ws = wb.sheet_by_name(sn)
        print(f"\n=== Sheet: {sn} ({ws.nrows} rows, {ws.ncols} cols) ===")
        
        # Column widths
        print("\nColumn widths:")
        for c in range(ws.ncols):
            ci = ws.colinfo_map.get(c)
            if ci and not ci.hidden:
                print(f"  Col {c} ({chr(65+c)}): width={ci.width}")
        
        # Merged cells
        if ws.merged_cells:
            print("\nMerged cells:")
            for r1, r2, c1, c2 in ws.merged_cells:
                print(f"  {chr(65+c1)}{r1+1}:{chr(65+c2)}{r2+1}")
        
        # Unique fonts
        fonts_seen = {}
        for r in range(ws.nrows):
            for c in range(ws.ncols):
                val = ws.cell_value(r, c)
                if val != '':
                    xf = wb.xf_list[ws.cell_xf_index(r, c)]
                    font = wb.font_list[xf.font_index]
                    key = (font.name, font.height/20, font.bold)
                    if key not in fonts_seen:
                        fonts_seen[key] = []
                    fonts_seen[key].append((r, c, str(val)[:30]))
        
        print("\nFonts used:")
        for k, cells in sorted(fonts_seen.items(), key=lambda x: -len(x[1])):
            print(f"  {k[0]}, {k[1]}pt, bold={k[2]} ({len(cells)} cells)")
        
        # Unique number formats
        fmts_seen = {}
        for r in range(ws.nrows):
            for c in range(ws.ncols):
                val = ws.cell_value(r, c)
                if val != '' and isinstance(val, (int, float)):
                    xf = wb.xf_list[ws.cell_xf_index(r, c)]
                    fmt_obj = wb.format_map.get(xf.format_key)
                    fmt_str = fmt_obj.format_str if fmt_obj else 'General'
                    h_align = xf.alignment.hor_align
                    if fmt_str not in fmts_seen:
                        fmts_seen[fmt_str] = {'count': 0, 'h_align': h_align}
                    fmts_seen[fmt_str]['count'] += 1
        
        print("\nNumber formats:")
        for fmt, info in sorted(fmts_seen.items(), key=lambda x: -x[1]['count']):
            print(f"  \"{fmt}\" h_align={info['h_align']} ({info['count']} cells)")

if __name__ == '__main__':
    inspect(sys.argv[1])
