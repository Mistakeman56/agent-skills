---
name: canvas-game-dev
description: Use when building or debugging a single-file HTML5 canvas game (render loop, camera, projectiles, procedural terrain).
---

# 浏览器 Canvas 游戏：开发与运行时排障

单文件 HTML5 canvas 游戏（无构建、无依赖）。典型场景：the user's LAN入口 `/game/` 塔车炮击——回合制、丘陵地形、抛物线弹道、镜头跟随/缩放、可破坏外壳。源文件 `/root/nav-game.html`。

部署管线/cookie/像素验证见 `nav-monitor`；视觉复核见 `image-analysis`。本 skill 只记 canvas 特有的坑。

## 部署管线（每次走完，别跳）

```python
from hermes_tools import terminal
import re
html = open('/root/nav-game.html', encoding='utf-8').read()
open('/tmp/g.js', 'w').write(re.search(r'<script>(.*)</script>', html, re.S).group(1))
print(terminal('node --check /tmp/g.js && cp /root/nav-game.html /var/www/nav/game/index.html && echo DEPLOYED')['output'])
```

- **必须先抽 `<script>` 再 `node --check`**：对 HTML 直接跑 node 会报错，抽出的才是真语法检查
- 先 check 再 cp；语法错上线 = 用户打开白屏
- URL 加 `?v=N` 绕浏览器缓存

## ⚠️ TypedArray 必须整数下标，读写两侧都静默失效

```js
terrain[x]                // Float64Array，x 为浮点 → undefined
ctx.lineTo(x, undefined)  // → NaN → 整条 path 作废 → 整块地形不画，且不报任何错
```

- typed array 下标必须整数；普通对象/数组才会把 `arr[33.7]` 当字符串键处理
- 相机/屏幕坐标换算几乎必然是浮点，所以**症状是「镜头一动这东西就消失」**：开局整数位置正常，一动就没了；弹道高低、是否缩放都与此无关
- 修法：循环边界 `Math.floor`/`Math.ceil`，其他读点 `Math.round`
- **同一下标问题有读、写两种失效，都完全静默**：读方向 `ctx.lineTo(x, undefined)` → NaN 废掉整条 path（不画）；写方向 `if (terrain[i] < nt)` 里 `terrain[i]` 是 `undefined` → 比较恒 false → **整个挖掘/碰撞分支一次都不执行**（症状是「怎么打地表都不变」，没有任何报错）
- 浮点来源不只是相机换算：`for (let dx=-r; dx<=r; dx++)` 里的 `r` 若是 `半径×缩放`（`22*1.8=39.6`）就必然产生浮点下标——**凡是用步进循环的，上界先 `Math.round`**
- 改完全局排查同类点（`grep -n 'terrain\['`），别只修报错那一行

## ⚠️ 别用 `window.X = wrapper` 给运行中的游戏循环插桩

想统计某内部函数被调用次数时，不要从外部包一层替换它：游戏循环内部是词法引用，替换后 wrapper 的 this/闭包链会断，**整个物理循环静默停摆**（`acc` 冻住、`life` 停 0、镜头不动），症状和真 bug 一模一样。

正确做法：

1. **只读状态变量**（`projs.length`/`state`/`turn`/`cam.x`）采样，不做任何替换
2. 真要计数就在源文件里加 `window.__n++` 再走部署管线
3. 插桩后物理突然全停 → **先撤探针重测**再下结论，很可能是自己造的

## 隐藏标签页不渲染、不推进（最贵的误诊源）

标签页 hidden 时 `requestAnimationFrame` 被节流到 0fps，于是同时出现三个症状：AI 回合卡住、`projs` 永不落地、截图全黑。这三个**都不是游戏 bug**，但长得跟「碰撞没生效」「地形被改没了」「镜头一动就消失」一模一样。

- **测试侧**：不等 rAF，测试循环里手动 `js("stepFixed(16.67)")` 跑物理、`js("render()")` 跑画面（是**调用**它，别重定义——见上文「别用 `window.X = wrapper` 插桩」）
- **产品侧兜底**：`tick` 里 cap 改 `document.hidden?1000:120` + `while(acc>=STEP&&guard<70)`，否则玩家切出标签页再切回来会卡死
- 排障顺序：**先确认标签页是不是 hidden，再去找游戏逻辑**。这一条已经导致过连续多次误诊

## ⚠️ 根因必须解释用户报的每一个现象

用户报「镜头跟炮弹时地形消失」，按弹道高度/镜头拉远修了一版并验证通过。用户回「**就算把炮弹打得很低地形也会消失**」——低抛弹道平、镜头几乎不上移，旧根因解释不了，真因另有其（typed array 那条）。

- 收到反馈先把用户描述的**所有情形列成清单**，逐条用同一根因解释；解释不通的就是根因错了
- 只在自己挑的场景验证通过 ≠ 修好，要覆盖用户提到的全部边界（高/低、快/慢、有无缩放）
- 用户明确否定你的诊断方向时，**先重找能覆盖全部现象的根因**，不要在旧根因上打补丁

## 单发改齐射（多弹头）的改造清单

`proj` 改 `projs[]` 前先 `grep -n 'proj'` 列全部引用点，漏一处就有一处静默失效：

| 位置 | 改成 |
|---|---|
| 镜头跟随 `camGoal()` | 跟最靠前那枚（`p.x*p.dir` 最大者） |
| 推进 `stepFlight()` | 倒序遍历 + 命中 `splice`，**全落地才 `endShot()`** |
| 状态判断 `state==='flight'` | 配套 `projs.length` 判空 |
| 开局重置 `startGame()` | 清空数组 |
| 绘制 `drawProj()` | 遍历画拖尾+弹体，`delay>0` 跳过（错帧发射） |

散布 `off=(k-(N-1)/2)*0.017`（±3.4°），瞄准辅助线同步画 N 条且中间最亮，否则玩家看不出会打散。飘字三件套都要挂进循环：`addFloat` 入队、`stepFloats` 上移渐隐、`drawFloats` 用 `strokeText` 描边（不描边压在亮背景上看不清）。

**推进循环里同时删和加，必须倒序遍历**：`for(let i=arr.length-1;i>=0;i--)` 里 `splice(i,1)` 删、`push()` 加是安全的——新元素落在下标 ≥ 旧 length > i，本轮不会被访问到，等于天然"新增物下一帧才生效"，不会漏判也不会重复判。正序遍历一删就错位。

## ⚠️ 浮在程序化地形上的标记/区域，位置必须钳到世界内

按 `terrain[x] + 偏移` 摆放的悬浮物（倍数区、检查点、收集物），地形低的那局会把它顶出世界边界（实测落到 y=9 贴着顶边）。

```js
const y = Math.max(56, Math.min(VH - 70, terrain[x] + offset));
```

上下界都要：上界防飞出世界、下界防埋进山里看不见。**别只在你测的那一局地形上看着正常就交付**——地形是随机的，摆位要在最坏地形下也成立。

## 弹头穿过触发体积：每枚只吃一次

弹头可能反复进出同一块区域（穿过→绕回→再穿），不加去重就会无限裂变把浏览器卡死。给弹头挂一个引用记它已经吃过的体积：

```js
if (p.zid === z) continue;   // 引用比较，别用 id 字符串（同名区域会误判）
... p.zid = z;
```

裂变/增殖一律加**总数上限**（`PROJ_CAP`，150 量级），超限后 `Math.min(PROJ_CAP-projs.length, 新增数)` 截断。没有上限时一次 ×10 穿越能瞬间生成几百弹，每枚都要跑 hitTest，帧率直接崩。

## ⚠️ 瞬时峰值不能靠轮询测，要在源码里打点

想测"峰值弹数"这类瞬态量，用 `setInterval`/轮询每 60ms 读一次 `projs.length` 是不够的——弹头在几帧内落地就会漏拍，你会读到一个看起来随机、但根本不是 bug 的数字。

瞬态峰值、瞬时命中数、单帧内的状态翻转，**只能在被测代码里 `window.__peak=Math.max(window.__peak,arr.length)` 打点**，再走部署管线读回。轮询只适合慢变量（`state`/`turn`/`cam.x`，变化间隔以秒计）。

**判据**：同一个量测出两个差一个数量级的结果时，先怀疑测量手段，再怀疑被测逻辑——但**在打点确认之前，不要对用户断言是哪一种**，两种可能都要如实说出来。

## ⚠️ 可破坏地形：三个约束缺一不可

挖掘函数写错的两种后果是「看不到破坏」和「一下挖穿世界」，都由下面三条堵住：

1. **锚点取当前地表，别用弹头的 y**：`vy` 大时一帧下落几十 px，弹已经钻进地下，用它的 y 起算半径会一口气挖到封顶。`const sy = Math.min(cy, terrain[ix])` 从地表往下挖。
2. **深度封顶**：生成地形后存 `terrainFloor[]`，挖掘 `cap = Math.min(VH-6, terrainFloor[ix] + MAXDIG)`，否则几发齐射能把世界底凿穿。
3. **半径 = 玩家要打几发**：一发凿的深度约等于半径。想让「炸开一座山」需要十几发就取 ~20px 量级；`r*3` 这种一发就抹平整个地标。**先定节奏再反推半径**，别反过来。

配套两条设计规则：

- **可达性检查进场走廊，不能只查中心点**。标记画在地形层之前（山体自然盖住 = 埋着）是「埋藏」的正确实现，但如果触发判定只看中心点，会出现「露出来了却打不着」——两侧山壁仍是实心，弹撞在坡上。判定区间 = 物本体 ± 进出场余量，整段地表都要降到物的下方。
- **消耗型触发（每区只吃一次的裂变/加成）把计数器放进推进循环每帧递减**。只在触发时赋值、从不递减，那块区域整局只生效一次，而测试看起来像「判定坏了」。

## 固定峰顶：别用 clamp 造地标

```js
terrain[x] = Math.max(78, terrain[x] - bump)   // ❌ bump 吃满余量的地方全被钳成 y=78 → 平顶台地
```

从随机底噪里「减出」山峰有两个毛病：峰高/峰位随局漂移，余量吃满后会被下界钳成一段平台（山变台地，「很高的山」不成立）。改成固定峰顶向两侧地面过渡，**只压低不抬高**：

```js
const shape = Math.pow(Math.max(0, 1-t*t), 1.35);   // 1=峰顶 → 0=山脚
const want  = PEAK + (1-shape)*(ground - PEAK);
terrain[x] = Math.min(ground, want);                 // 噪声保留成山体纹理
```

验收别只看这一局：**抽 20+ 点打印剖面**（`Array.from({length:23},...terrain[...])`），确认峰位恒在 `cx`、剖面单调升到峰顶再降、没有一段连续 N px 等值。地形随机，单局好看是运气。

## ⚠️ 回归真实对局，别只测手工注入的弹

手工造弹（`projs=[{...}]`）能快速验单点机制，但**判负/换手链路必须走游戏自己的状态机**：

- 换手多用 `setTimeout(beginTurn, 850)`——手动驱动物理时这个定时器不触发，回合卡在 `state==='busy'`。测的时候每轮打完手动 `state='play'; turn=...` 推进
- 瞄准一律用游戏自带的解算（`solveShot(shooter,target)`）：手算落点会忽略炮口高度与 `POW_MAX` clamp，射程静默差几百 px，症状看起来像「子弹打不到」
- **改过 `POW_MAX`/`G`/`WW` 之后，历史测试里硬编码的 power 和角度全部作废**，重算再测
- 判负读游戏实际持有的变量名，别假设存在没定义的全局——`ReferenceError: winner is not defined` 是测试脚本写错，不是游戏 bug，别顺着它去改游戏
