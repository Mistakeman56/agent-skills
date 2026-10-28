# 覆盖层 IK 生物：可复用片段

## 1. 锚点提取（逐行文本框）

```js
const SEL = 'p,a,li,h1,h2,h3,td,th,dt,dd,.reference,.citation,.tax,.metadata';
function anchors(){
  const out = [];
  for (const el of document.querySelectorAll(SEL)) {
    if (!el.offsetParent && el.tagName !== 'BODY') continue;   // 跳过隐藏元素
    const r = document.createRange();
    r.selectNodeContents(el);
    for (const b of r.getClientRects()) {
      if (b.width < 4 || b.height < 4) continue;               // 丢掉退化矩形
      out.push({ x: b.right, y: b.top + b.height * 0.5, w: b.width, h: b.height, el });
    }
  }
  return out;   // 逐行！不是逐元素
}
```
取 `b.right`（行尾）比取行中更容易看起来「踩在字上」；`b.top + h/2` 对齐基线中部。

## 2. 半径内选点（防止把肢体拉成直线）

```js
function pickNear(anchors, px, py, maxR){
  const cand = anchors
    .map(a => ({ a, d: (a.x - px) ** 2 + (a.y - py) ** 2 }))
    .filter(o => o.d <= maxR * maxR)
    .sort((p, q) => p.d - q.d)
    .slice(0, 6);
  if (!cand.length) return null;                 // 附近没字 → 接触点原地不动 ✓
  const pick = cand[Math.floor(Math.random() * cand.length)];
  return { x: pick.a.x + (Math.random() - .5) * 2.4,
           y: pick.a.y + (Math.random() - .5) * 2.4 };
}
const R = size * 1.35;   // 经验值：再远 IK 就把腿拉直了
```

## 3. 两节骨 IK

```js
function solve(ax, ay, tx, ty, L1, L2, side){
  let dx = tx - ax, dy = ty - ay;
  let d = Math.hypot(dx, dy);
  const maxReach = (L1 + L2) * 0.999, minReach = Math.abs(L1 - L2) * 1.001;
  if (d > maxReach) { const k = maxReach / d; dx *= k; dy *= k; d = maxReach; tx = ax + dx; ty = ay + dy; }
  if (d < minReach) d = minReach;
  const A = Math.acos(Math.min(1, Math.max(-1, (L1*L1 + d*d - L2*L2) / (2*L1*d))));
  const base = Math.atan2(dy, dx);
  const kx = ax + Math.cos(base + A * side) * L1;
  const ky = ay + Math.sin(base + A * side) * L1;
  return { kx, ky, d };
}
```
- 骨长要**大于静止距离**（L1≈0.80s / L2≈0.88s 对静止距离 ~1.0s）→ 关节弯 40~60° 才看得见。
- `side` 用叉积定：`const side = (dx * (-Math.sin(base)) + dy * Math.cos(base)) > 0 ? -1 : 1;` 关节才朝外。
- 折线用「附着点 → 膝 → 跗节（在膝到脚之间再加一点、垂直方向偏 0.15~0.2 骨长）→ 脚」，否则看不出关节 ✗。

## 4. 步态状态机（交替四足）

```js
// 每肢：phase ∈ {planted, swinging}；swingT 归一化进度
// 交替规律：第 i 肢在 ((i%2) ^ (Math.floor(i/2)%2)) 的相位上摆动
update(dt){
  if (this.state === 'planted') {
    // 支撑相：脚钉死在世界坐标，随页面滚动只做 scroll 增量换算
    this.foot.y += this.scrollBase - worldScroll;   // 别让它跟躯干走
    const dist = Math.hypot(this.foot.x - this.sp.x, this.foot.y - this.sp.y);
    if (dist > this.maxStretch || this.timer > this.maxHold) { this.state = 'swinging'; this.swingT = 0; }
  } else {
    this.swingT += dt / this.swingDur;
    if (this.swingT >= 1) {
      this.state = 'planted'; this.timer = 0;
      const t = pickNear(anchors, this.rest.x, this.rest.y, R);
      if (t) this.foot = t;
    }
  }
}
```
自检指标：**已钉住数量** 应约等于总肢数一半并缓慢变化（7→4→3 ✓）；长期 0~1 = 速度/相位算错。

## 5. 度量注入（验证脚本里跑，输出硬数字）

```js
() => {
  const textRects = [];
  for (const el of document.querySelectorAll('p,li,td,a,h2,.reference')) {
    const r = document.createRange(); r.selectNodeContents(el);
    for (const b of r.getClientRects()) if (b.width > 4 && b.height > 4) textRects.push(b);
  }
  const feet = [...document.querySelectorAll('polyline')].flatMap(p => {
    const pts = p.getAttribute('points').trim().split(/\s+/);
    const [x, y] = pts[pts.length - 1].split(',').map(Number);
    return isFinite(x) && isFinite(y) ? [{ x, y }] : [];
  });
  const dists = feet.map(f => {
    let m = Infinity;
    for (const b of textRects) {
      const dx = Math.max(b.left - f.x, 0, f.x - b.right);
      const dy = Math.max(b.top - f.y, 0, f.y - b.bottom);
      m = Math.min(m, Math.hypot(dx, dy));
    }
    return m;
  }).sort((a, b) => a - b);
  return { feet: feet.length, median: dists[dists.length >> 1], within3px: dists.filter(d => d <= 3).length };
}
```
期望：`median ≈ 0.00`、`within3px` 占绝大多数。**采样两次（间隔 2s）对比脚的坐标**，证明真的在移动（不是静止摆造型）。

## 6. 放大裁切 + 录屏 + 转码

```python
# 放大看细节（vision 在整页图上抓不到 4px 的眼睛）
await page.screenshot(path='/tmp/zoom.png', clip={'x': cx-150, 'y': cy-150, 'width': 300, 'height': 300})

# 录屏（交付用）
ctx = await b.new_context(viewport={'width':1000,'height':1000},
                          record_video_dir='/tmp/vid',
                          record_video_size={'width':1000,'height':1000})
await page.mouse.wheel(0, 420)      # 滚动几次，展示重新踩点
await page.mouse.click(300, 700)    # 点击加一个实例
await ctx.close()                   # 关上下文才会 flush 视频
```
```sh
ffmpeg -i /tmp/vid/*.webm -vf 'scale=1000:1000,fps=30' -c:v libx264 -preset medium \
  -crf 21 -pix_fmt yuv420p -movflags +faststart demo.mp4
```
交付时回复里写 `MEDIA:/绝对路径/demo.mp4`。
