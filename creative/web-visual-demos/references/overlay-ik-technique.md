# 覆盖层 + IK + 步态：技术骨架

配套 SKILL.md 的「步骤 2/3」。这里是能被复制改改就用的骨架，不是完整产品代码。

## 1 布局：两层 SVG

深色身体 + 发光腿这种组合，**一定要拆两层**，否则 `mix-blend-mode: screen` 会把近黑填充吃掉（症状是「腿从一点放射」，不会想到是混合模式）：

```html
<svg id="glowLayer" class="stage"></svg>  <!-- screen 混合：腿、丝线、辉光 -->
<svg id="bodyLayer" class="stage"></svg>  <!-- normal 混合：深色身体（画在上层，天然遮住穿过去的腿） -->
```
```css
.stage{position:fixed;inset:0;width:100%;height:100%;pointer-events:none;overflow:visible}
#glowLayer{z-index:3;mix-blend-mode:screen}
#bodyLayer{z-index:4}
```

要素分布：**腿 / 丝 → glowLayer**；**身体两节 + 眼睛 + 螯肢 → bodyLayer（身体先 append，小部件后 append = 画在身体之上）**。

## 2 锚点：逐行文本框，不是元素框

```js
const SEL = 'p,a,li,h2,h3,td,th,.reference,.tax,.navbox';
function collectAnchors(){
  const out = [];
  for (const el of document.querySelectorAll(SEL)){
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue;
    // 关键：Range 把元素切成逐行的小矩形
    for (const node of el.childNodes){
      if (node.nodeType !== 3 || !node.textContent.trim()) continue;
      const r = document.createRange(); r.selectNodeContents(node);
      for (const box of r.getClientRects()){
        if (box.width < 4 || box.height < 4) continue;
        out.push({x: box.left + box.width * (0.06 + Math.random()*0.88),
                  y: box.top + box.height * (0.3 + Math.random()*0.4)});
      }
    }
  }
  return out;
}
```
规则：
- **必须逐行**（`getClientRects()` 而非元素框）—— 宽段落用元素框取点会落到右侧空白
- 每次滚动/尺寸变化后重采（滚动过程中采会拿到中间态坐标）
- 锚点是**建议位**，不是硬目标；脚只在自己**附近**的锚点里挑（见下方半径规则）

## 3 IK：两节骨头 + 余弦定理

```js
const cosA = (L1*L1 + d*d - L2*L2) / (2*L1*d);   // 股节与「体→脚」夹角
const A = Math.acos(Math.max(-1, Math.min(1, cosA)));
const base = Math.atan2(fy - ay, fx - ax);        // 体上附着点 → 脚
const sgn  = side > 0 ? 1 : -1;                    // 左右腿膝弯方向相反
const kx = ax + Math.cos(base + sgn*A) * L1;
const ky = ay + Math.sin(base + sgn*A) * L1;       // 膝
// 再在「膝→脚」之间取一个带横向偏移的点做跗节，避免整条腿共线看起来像一根直线
```

参数（体型记作 `s`）：
- `L1 ≈ 0.80·s`、`L2 ≈ 0.88·s`（骨头总长 ≈ 静止距离的 1.6–1.9 倍 → 膝角 45°–60°，肉眼可见折角）
- 附着点：左右 `±0.24·s`，纵向 `-0.34·s … +0.30·s`（八条腿沿体前到后分布）
- 跗节横向偏移 `≈0.20·s`（太小 = 直线感，太大 = 断腿感）
- **`d` 必须 clamp 到 `L1+L2`**，否则 `acos` 出 NaN → 整条腿消失
- 锚点挑选半径 `≤ 1.35·s`：太远会把腿拉成笔直射线（视觉上「从一点放射」）

## 4 步态：世界钉脚 + 施密特触发

每条腿一个状态机，**支撑时脚钉在世界坐标**（不随身体平移）—— 这是「爬」与「滑」的唯一区别：

```js
const leg = { state:'stance', foot:{x,y}, anchor:{x,y}, p0:{x,y}, t0:0 };
function step(dt, body){
  const attach = worldAttach(leg);                 // 体上附着点（跟着身体走）
  if (leg.state === 'stance'){
    const dist = Math.hypot(leg.foot.x-attach.x, leg.foot.y-attach.y);
    if (dist > 1.55*leg.reach) {                   // 超出伸展极限 → 换步
      leg.state = 'swing';
      leg.p0 = {...leg.foot};
      leg.anchor = pickNear(leg.foot, 1.35*body.size);   // 只挑附近的锚点
      leg.t0 = now;
    }
  } else {
    const k = Math.min(1, (now - leg.t0) / SWING_MS);    // SWING_MS ≈ 200–420ms
    leg.foot.x = lerp(leg.p0.x, leg.anchor.x, k);
    leg.foot.y = lerp(leg.p0.y, leg.anchor.y, k) - Math.sin(k*Math.PI) * 0.5*body.size; // 抬起弧线
    if (k >= 1){ leg.state='stance'; leg.foot.x=leg.anchor.x; leg.foot.y=leg.anchor.y; }
  }
}
```

配套规则：
- **限制同时抬起的腿数**（交替四足：每侧最多 2 条在摆动）→ 用「相邻腿不允许同时摆动」的排队规则，否则会出现「一起跳」的怪相
- 身体速度用 **px/秒**；`vy*dt*60` 是 60 倍速，症状是 `planted ≈ 0`
- 触底/触顶要**反弹**（`vy = -Math.abs(vy)`）而不是传送，否则身体瞬移、腿全乱

## 5 解剖：让它像生物而不是几何题

- 身体**两节**：腹部大椭圆（`rx≈0.50·s, ry≈0.60·s`，画在体后）+ 头胸部小椭圆（`rx≈0.34·s, ry≈0.40·s`）
- 眼睛：头胸前缘一排 8 颗（`r ≈ 0.13·s`，亮色）—— 画在**身体之上**，否则被挡住
- 螯肢 / 须肢：前缘 2 条短折线
- 腹部纹理：2–3 条折线，颜色用关节色
- 腿描边 `≈0.075·s`（细于 `0.05·s` 时关节折角在缩放视图里会糊掉）

## 6 交互与状态显示

- `scroll` → 重采锚点（脚要能跟着新内容重新踩）
- `click` → 追加一只（默认 2 只：多了线就乱、挡正文）
- 角标显示**可证伪的计数**：`FOOTHOLDS / CRAWLERS / FEET PLANTED` —— 这几个数字就是验证脚本的读数来源
