# Windows Event Log (.evtx) Analysis

## Quick Start

```bash
pip install --break-system-packages python-evtx
```

## Parse .evtx to XML

```python
from Evtx.Evtx import FileHeader
from Evtx.Views import evtx_file_xml_view
import xml.etree.ElementTree as ET
import re

filepath = "/path/to/file.evtx"
with open(filepath, 'rb') as f:
    buf = f.read()

# ⚠️ Offset is 0, NOT 0x1000
header = FileHeader(buf, 0)
for xml_str, record in evtx_file_xml_view(header):
    # Strip xmlns for ET parsing
    xml_str = re.sub(r'xmlns[^"]*"[^"]*"', '', xml_str)
    root = ET.fromstring(xml_str)
    sys = root.find('.//System')
    # ... extract fields
```

## Key XML Structure

```xml
<Event>
  <System>
    <Provider Name="SOURCE_NAME"/>
    <EventID>13</EventID>
    <Level>2</Level>  <!-- 1=Critical, 2=Error, 3=Warning, 4=Info -->
    <TimeCreated SystemTime="2026-06-18T04:37:59"/>
  </System>
  <EventData>
    <Data Name="param1">value</Data>
  </EventData>
  <RenderingInfo>
    <Message>Human-readable message</Message>
  </RenderingInfo>
</Event>
```

## Reliability Monitor XML (RelMonReport)

Windows Reliability Monitor exports as UTF-16LE XML. Convert first:
```bash
iconv -f UTF-16LE -t UTF-8 file.XML
```

Key elements:
- `<GraphData>` — reliability score over time (hourly data points)
- `<RacEvents>` — event list with `<Source>`, `<Problem>`, `<Time>`, `<Impact>`
- `<WerEvents>` — Windows Error Reporting events with `<State>`

Common Impact values: 关键 (Critical), 警告 (Warning), 信息 (Info)

## Known GPU Error Patterns (nvlddmkm)

| EventID | Meaning | Severity |
|---------|---------|----------|
| 13 | GPU fell off bus / display driver timeout | ERROR — hardware issue |
| 141 | GPU has stopped responding | ERROR — TDR failure |
| 153 | GPU physically removed / hardware failure detected | ERROR — serious hardware |
| 4101 | Display driver stopped responding and recovered | WARNING — recovered |

**Event 13 + 153 in sequence = GPU hardware failure** (not just driver crash). Causes:
1. Loose 12VHPWR power connector (most common on 4080/4090)
2. GPU overheating
3. PSU insufficient/unstable power delivery
4. PCIe slot contact issue
5. VRAM or GPU core failure

## Filtering Events

```python
# Filter by severity
interesting = [e for e in events if e['level'] in ('1', '2')]

# Filter by keyword
keywords = ['whea', 'nvlddmkm', 'gpu', 'display', 'hardware', 'bugcheck']
interesting = [e for e in events 
               if any(kw in (e['provider'] + e['data']).lower() for kw in keywords)]
```
