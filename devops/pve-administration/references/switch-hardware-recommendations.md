# Network Switch Hardware Recommendations

## 48-Port 100Mbps Unmanaged Switches

For users needing 48+ port 100Mbps switches (legacy deployments, budget constraints):

| Brand | Model | Ports | Type | Year | Price (Used) | Notes |
|-------|-------|-------|------|------|--------------|-------|
| **TP-Link** | **TL-SF1048** | 48×10/100M | Unmanaged | 2010+ | ¥60-100 | Most common, reliable |
| **TP-Link** | **TL-SF1048D** | 48×10/100M | Unmanaged | 2012+ | ¥50-80 | Budget version |
| **Cisco** | **SF100-48** | 48×10/100M | Unmanaged | 2012+ | ¥100-150 | Cisco Small Business line |
| **D-Link** | **DES-1048** | 48×10/100M | Unmanaged | 2010+ | ¥60-90 | Decent quality |

**Search keywords for Xianyu (闲鱼):**
- `TL-SF1048`
- `SF100-48`
- `48口百兆交换机`

## 48-Port Gigabit Managed Switches

For modern deployments needing 48+ gigabit ports:

| Brand | Model | Ports | Type | Year | Price (Used) | Notes |
|-------|-------|-------|------|------|--------------|-------|
| **H3C** | **S5130-52S-EI** | 48GE+4SFP+ | Managed | 2015-2017 | ¥300-500 | Enterprise workhorse |
| **H3C** | **S5560X-52S-EI** | 48GE+4×10GE SFP+ | Managed | 2018-2020 | ¥500-800 | Higher end |
| **Huawei** | **S5720-52P-LI** | 48GE+4SFP | Managed | 2017-2019 | ¥400-600 | Huawei enterprise |
| **Huawei** | **S5720-52X-LI** | 48GE+4×10GE SFP+ | Managed | 2018-2020 | ¥500-700 | 10G uplinks |
| **Ruijie** | **RG-S5750-48GT4XS-H** | 48GE+4×10GE SFP+ | Managed | 2018-2020 | ¥400-600 | Good value |

**Search keywords for Xianyu:**
- `H3C S5130-52S-EI`
- `H3C S5560X-52S-EI`
- `华为 S5720-52P-LI`
- `锐捷 S5750-48GT4XS`

## 24-Port Gigabit Unmanaged Switches

For smaller deployments (8-24 devices):

| Brand | Model | Ports | Type | Price (New) | Notes |
|-------|-------|-------|------|-------------|-------|
| **TP-Link** | **TL-SG1008D** | 8GE | Unmanaged | ¥30-50 | Budget 8-port |
| **TP-Link** | **TL-SG1016D** | 16GE | Unmanaged | ¥60-80 | Budget 16-port |
| **H3C** | **S1224** | 24GE | Unmanaged | ¥80-120 | H3C quality |

## User's Current Setup

- **Switch**: H3C S3600V2-52TP-SI (48×100M + 4×GE SFP)
- **Age**: 2010-2012 (12-15 years old)
- **Type**: Managed (SI = Standard Intelligence)
- **Issue**: Intermittent disconnections on consecutive ports
- **Workaround**: Spread devices across non-adjacent ports

## Selection Criteria

1. **Unmanaged > Managed** for simple plug-and-play deployments
2. **Newer is better** — 2015+ models have better reliability
3. **Enterprise brands** (H3C, Huawei, Cisco, Ruijie) > Consumer brands (TP-Link, D-Link) for 48+ ports
4. **Check power supply** — Old switches often have failing capacitors in PSU
5. **Test all ports** — Second-hand switches may have dead ports
