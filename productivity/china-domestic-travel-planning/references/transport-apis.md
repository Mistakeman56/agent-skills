# 国内交通查询 API（无鉴权 JSON）

浏览器访问携程/12306 会被反爬拦截（携程 432、12306 验证码），但底层 JSON API 可直接 curl 访问。以下方法均在 2026-07 实测可用。

## 1. 携程机票最低价 API

返回某航线未来 2 个月每日最低价（含税口径，多为廉航最低价）。

**URL：**
```
https://flights.ctrip.com/itinerary/api/12808/lowestPrice?flightWay=Oneway&dcity=HGH&acity=DLC&dcityname=杭州&acityname=大连&depDate=2026-08-11&adult=2
```

**参数：**
- `flightWay=Oneway` 单程
- `dcity` / `acity`：机场三字码（HGH=杭州, DLC=大连, SHA=上海, PVG=上海浦东, SZV=苏州, HGH=杭州）
- `dcityname` / `acityname`：中文城市名（URL 编码）
- `depDate=YYYY-MM-DD`：出发日期
- `adult=2`：人数

**调用（注意 unset 代理）：**
```bash
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u CLASH_PROXY \
  curl -s "https://flights.ctrip.com/itinerary/api/12808/lowestPrice?flightWay=Oneway&dcity=HGH&acity=DLC&dcityname=%E6%9D%AD%E5%B7%9E&acityname=%E5%A4%A7%E8%BF%9E&depDate=2026-08-11&adult=2" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
```

**响应：**
```json
{"data":{"oneWayPrice":[{"20260811":450,"20260812":500,...}],...},"status":0,"msg":"success"}
```
`oneWayPrice[0]` 是 `{日期YYYYMMDD: 最低价元}` 映射。取目标日期价格即可。

**局限：**
- 只给最低价，不含航班号/时刻/航司。需要具体航班时用 `products` 接口，但该接口 2026-07 已返回"接口下线"（`{"status":0,"data":{"error":{"msg":"接口下线"}}}`），暂时不可用
- 报价是"最低价"口径，向用户说明

## 2. 12306 高铁余票/车次 API

**关键：必须先 GET init 页面拿 cookie，再 queryG 才有数据。**

**第一步（拿 cookie）：**
```bash
curl -s "https://kyfw.12306.cn/otn/leftTicket/init" \
  -c /tmp/12306.cookie -b /tmp/12306.cookie \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)" -o /dev/null
```

**第二步（查车次）：**
```bash
curl -s "https://kyfw.12306.cn/otn/leftTicket/queryG?leftTicketDTO.train_date=2026-08-10&leftTicketDTO.from_station=SZH&leftTicketDTO.to_station=HZH&purpose_codes=ADULT" \
  -c /tmp/12306.cookie -b /tmp/12306.cookie \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
  -H "Referer: https://kyfw.12306.cn/otn/leftTicket/init"
```

**参数：**
- `leftTicketDTO.train_date=YYYY-MM-DD`
- `leftTicketDTO.from_station` / `to_station`：**车站电报码**（SZH=苏州, HZH=杭州, SHH=上海, BJN=北京, DLN=大连 等），不是三字码
- `purpose_codes=ADULT` 成人

**响应：** `data.result` 是 URL 编码的 `|` 分隔数组，每行一个车次。**字段索引（2026-08 实测修正）：**
```
[0]=预订token  [1]=预订  [2]=内部码  [3]=车次号  [4]=始发站码  [5]=终到站码
[6]=上车站码   [7]=下车站码  [8]=出发时刻  [9]=到达时刻  [10]=历时  [11]=Y
[13]=日期(YYYYMMDD)  [14]=余票标记(3=有票)  [16]/[17]=其他票种  [30]=商务/无
```
⚠️ **`[13]` 是日期不是二等座！`[14]` 是无座/余票标记不是一等座！** 早期解析误把 [13]/[14] 当座位余票导致报错票价。**座位余票字段不稳定**，不要依赖字段索引给精确余票数——可靠做法：告诉用户"有票/无票"（[14]==有票），精确余票让用户在12306 APP确认。用 Python `urllib.parse.unquote` + `split('|')` 解析。

**⚠️ PITFALL: 返回的车次可能不是目标站上车！** 12306 按"走廊"返回车次，`queryG(from=SZH,to=HZH)` 会混入上车站=盛泽/苏州南/苏州园区/张家港 的车次（2026-08 实测，用户当场质疑 G3309\"途径站没有苏州\"）。**必须用 station_name.js 把每条车次的 [4][5][6][7] 翻译成中文站名，只推荐 [6]==目标站 的车次**，回复中明确写\"苏州站上车\"。

**注意：** 若直接 queryG 返回 `{"c_url":"leftTicket/queryG","c_name":"CLeftTicketUrl","status":false}`，说明没带 cookie，先跑第一步。

**⚠️ PITFALL: queryG 返回 200 但 `result` 为空 = 站点代码用错了（2026-08 实测）。** 曾用机场三字码（SUH/HGH）查苏州→杭州，返回 HTTP 200 但 `result: []`，浪费多轮排查。12306 用的是**车站电报码**，不是机场三字码。**拿到任意站点电报码的方法：**
```bash
curl -s "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js" -H "User-Agent: Mozilla/5.0" -o /tmp/stations.js
python3 -c "
import re
data = open('/tmp/stations.js', encoding='utf-8', errors='ignore').read()
for m in re.findall(r'@[a-z]+\|([^\|]+)\|([A-Z]+)\|', data):
    if '苏州' in m[0] or '杭州' in m[0]:
        print(m[0], m[1])   # 苏州 SZH / 杭州 HZH
"
```
该文件包含全部车站 `@拼音|站名|电报码|...`，用正则取站名+电报码即可。常见：苏州=SZH、杭州=HZH、上海=SHH、大连=DLN。

## 3. 城市/机场三字码速查

| 城市 | 机场三字码（携程 dcity） | 车站电报码（12306） |
|------|--------------------------|---------------------|
| 上海 | SHA / PVG | SHH |
| 苏州 | SZV | SZH |
| 杭州 | HGH | HZH |
| 大连 | DLC | DLN |
| 北京 | PEK / PKX | BJN |
| 广州 | CAN | GZQ |

## 4. 高铁票价参考（2026）

- 苏州→杭州 二等座：约 ¥110-125/人
- 上海→苏州 二等座：约 ¥40-50/人
- 报价时按标准票价计算，实际以12306为准
