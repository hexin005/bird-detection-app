# 「青禾 · 果园守护」UI 风格提示词

> 用途：把本提示词交给任何 AI（或新成员），即可 1:1 复刻本项目 H5 界面的视觉与组件风格。
> 依据：`mobile/src/tokens.css`（v2 纸面·田园笔记）、`components-qh.css`、`styles.css`、`scene/src/`（3D HUD）。

---

## 提示词正文（复制以下全部内容使用）

你是一位资深移动端 UI 工程师，负责为「青禾 · 果园守护」——一个基于 YOLOv8 的果园鸟类监测与声波/红外驱鸟系统——生成 uni-app (Vue 3 + TS) H5 界面。你生成的每一页都必须严格遵循以下设计系统，不得自由发挥配色、字体或组件形态。

### 一、产品语境

- 场景：现代果园的数字化监测大屏 + 手机操作端。页面共 5 页：登录、监控（首页）、告警、控制（远程控制）、记录（鸟类档案/视频回放）。
- 用户在果园现场或办公室操作；界面同时会投屏演示，要求「像一份纸质巡护笔记，又像一台精密仪表」。
- 全部中文文案，语气克制、以数据说话，避免营销腔；设备均为模拟执行器时须有「不会控制真实硬件」的小字说明。

### 二、视觉基调：纸面 · 田园笔记（v2）

1. 底色是**暖纸**（不是纯白、不是冷灰），卡片是纯白纸片，描边是带绿的暖色细线——整体像贴在纸面上的标本卡。
2. **唯一重色是墨绿**：只允许出现在主按钮、选中态、「正在监测」徽标、底部导航选中胶囊。其余状态一律用低饱和语义色（暖沙/赤陶/叶绿/浅绿/中性）。
3. 荧绿 `#d3e856` 是**唯一的高亮亮色**，只出现在视频画面的检测框、扫描线和 3D 场景的科技元素上，绝不用于普通 UI。
4. 数字用等宽感字族（Inter）放大呈现，是页面的视觉主角之一（统计卡大数字）。
5. 标题用**宋体**（Source Han Serif SC 栈），与无衬线正文形成「笔记」气质。
6. 阴影极轻（低层叠），圆角偏大，触控目标 ≥44px。

### 三、设计令牌（直接复制为 tokens.css，组件内一律 var() 取值）

```css
page, :root {
  /* 品牌色：墨绿 */
  --brand-900:#22371f; --brand-800:#27402a; --brand-700:#34502f; --brand-600:#3f5c33;
  --brand-500:#4f6b3f; --brand-400:#7b9b63; --brand-300:#a7b78e; --brand-200:#cdd9b8;
  --brand-100:#e4eddc; --brand-50:#f4f6ea;

  /* 中性色：带绿的暖墨 */
  --ink-900:#232b1d; --ink-800:#2a3324; --ink-700:#43503e; --ink-600:#6d7f6c;
  --ink-500:#7c8472; --ink-400:#8a917f; --ink-300:#a3ab97; --ink-200:#b8bfa9; --ink-100:#c3cbb8;

  /* 表面：暖纸面 */
  --surface-canvas:#f3f1e7; --surface-card:#ffffff; --surface-raised:#fbfaf3;
  --surface-sunken:#edefdf; --surface-muted:#f7f5ec; --surface-video:#1c2318;
  --surface-mask:rgba(35,43,29,.5);

  /* 描边 */
  --line-strong:#dcd9c8; --line:#e9e6d7; --line-soft:#e5e2d2; --line-focus:#34502f;

  /* 语义色（bg / fg / line 三件套） */
  --warn-bg:#f5ebd5;   --warn-fg:#96682b;   --warn-line:#e7d5ae;    /* 待处理/需关注 */
  --danger-bg:#f3e4dd; --danger-fg:#9c5546; --danger-line:#e2c9be;  /* 失败/异常 */
  --success-bg:#e9f0dc;--success-fg:#56753f;--success-line:#d3e3c6; /* 完成/在线 */
  --info-bg:#e4eddc;   --info-fg:#3f6b49;   --info-line:#c8dcc0;    /* 进行中 */
  --neutral-bg:#edeee4;--neutral-fg:#6d7f6c;--neutral-line:#dde1d5; /* 未开始/已停止 */

  /* 检测框（视频画面上唯一亮色） */
  --detect-box:#d3e856; --detect-text:#22301f;

  /* 字号 */
  --text-2xs:9px; --text-xs:10px; --text-sm:11px; --text-base:12px; --text-md:13px;
  --text-lg:14px; --text-xl:15px; --text-2xl:18px; --text-3xl:24px; --text-title:25px;

  /* 字族（系统栈，不引外部字体） */
  --font-sans:"Noto Sans SC","PingFang SC","HarmonyOS Sans SC","Microsoft YaHei",sans-serif;
  --font-serif:"Source Han Serif SC","Noto Serif SC","Songti SC","SimSun",serif;
  --font-num:"Inter","SF Pro Text","Noto Sans SC",sans-serif;

  /* 行高 / 字距 */
  --leading-tight:1.3; --leading-snug:1.45; --leading-normal:1.65;
  --tracking-btn:2px; --tracking-caps:1px;

  /* 间距（4px 基准） */
  --space-1:4px; --space-2:6px; --space-3:8px; --space-4:10px; --space-5:12px;
  --space-6:14px; --space-7:16px; --space-8:20px; --space-9:24px; --space-10:32px;

  /* 圆角 */
  --radius-xs:6px; --radius-sm:9px; --radius-md:12px; --radius-lg:13px; --radius-xl:14px;
  --radius-2xl:16px; --radius-3xl:18px; --radius-sheet:20px; --radius-pill:999px;

  /* 阴影 */
  --shadow-xs:0 1px 3px rgba(36,43,28,.06); --shadow-sm:0 2px 6px rgba(36,43,28,.08);
  --shadow-btn:0 4px 12px rgba(41,61,33,.25); --shadow-float:0 6px 16px rgba(36,43,28,.12);
  --shadow-focus:0 0 0 3px rgba(52,80,47,.14);

  /* 动效 */
  --ease-out:cubic-bezier(.22,.61,.36,1); --ease-in-out:cubic-bezier(.4,0,.2,1);
  --dur-fast:120ms; --dur-base:200ms; --dur-slow:320ms;

  /* 尺寸 */
  --page-max:390px; --control-height:46px; --input-height:48px; --btn-height:44px;
  --touch-min:44px; --tabbar-height:78px; --statusbar-height:44px;
  --page-pad:14px; --section-gap:9px;
}
```

### 四、布局骨架（styles.css）

- `html,body,uni-app,uni-page,uni-page-body { height:100%; overflow:hidden }`，页面底 `--surface-canvas`。
- 手机壳 `.phone { width:390px; height:100vh; height:100dvh; margin:0 auto; display:flex; flex-direction:column; overflow:hidden; box-shadow:0 18px 60px rgba(31,47,38,.18) }`；≤420px 视口时占满全屏去阴影。
- 状态栏 `.statusbar { height:44px; flex-shrink:0; padding:0 24px; padding-top:env(safe-area-inset-top) }`，左「9:41」(font-num 15px 600)，右信号/WiFi/电池 SVG（填充 `--ink-900`）。
- 页面 `.page { display:none; flex:1 1 0%; min-height:0 }`，当前页 `.is-current { display:flex }`；内容区 `.page__content { flex:1 1 0%; min-height:0; overflow-y:auto; padding:var(--page-pad); display:flex; flex-direction:column; gap:var(--section-gap) }`。
- **内容区子元素一律 `flex-shrink:0`**（视频区等不许被压缩），滚动条细样式（6px、rgba(52,80,47,.22)）。
- 底部导航 `.qh-tabbar { height:78px; flex-shrink:0; }`。

### 五、uni-app 技术硬约束（必须照做，否则样式互相打架）

1. uni-app H5 会把 `<view>/<text>/<image>/<button>/<input>` 编译为 `uni-view/uni-text/uni-image/uni-button/uni-input`；选择器要同时兼容。
2. 框架样式表在应用样式**之后**加载，`uni-button` 自带 `padding:0 14px`、`margin-left/right:auto`、`::after` 边框、`border-radius`、`background`、`font-size:18px`。重置必须用**零特异性**写法：

```css
:where(button, uni-button) {
  margin:0 !important;   /* margin 必须 !important：框架的 auto 会把按钮挤到容器中间 */
  padding:0; border:0; border-radius:0; background:transparent; color:inherit;
  font:inherit; line-height:inherit; text-align:inherit; width:auto; min-width:0;
  -webkit-appearance:none; appearance:none;
}
:where(button, uni-button)::after { display:none !important; border:0 !important; content:none !important; }
```

3. 除上述两处 `!important` 外，**组件类禁止再用 `!important`**——class(0,1,0) 本来就压过框架元素选择器(0,0,1)。
4. 图标全部用内联 SVG（stroke 用具体色值，如 #44523E / #F5F7EC），不引图标库。
5. 不引入任何外部字体文件与 UI 组件库；动效只用 CSS transition/animation。

### 六、组件规范（类名即约定，值为权威）

**页头 `.qh-header`**（flex 两端对齐）：
- 左侧品牌块：`.qh-appname` 16px/600 墨色 + `.qh-mvp` 徽标（brand-100 底、brand-500 字、9px、字距 1px、圆角 6px）+ `.qh-site` 11px 次要灰。
- 页面大标题区 `.qh-titleblock`：`.qh-page-title` **宋体 25px/700 墨色** + 右侧状态徽标；副标题 `.qh-page-subtitle` 12px 灰。
- 右侧操作：`.qh-iconbtn`（40×40 白底圆、1px line-soft 描边、内联 SVG 22px）；「3D 视角」用 `.qh-3dbtn`（墨绿胶囊 28px 高、白字 11px、字距 1px）。

**状态徽标 `.qh-badge`**（胶囊 20px 高、10px 字、内含 5px 圆点 + 文本）：
`--ended/handled` success 底、`--new/processing` warn 底、`--running` **brand-700 底白字**、`--failed` danger 底。监控页 8 态映射：idle→neutral、starting→info、running→墨绿实底、stopped→neutral、ended→success、interrupted→warn、error→danger。

**连接条 `.qh-conn`**：brand-100 底、圆角 9px、高 30px，左「● 实时连接」（绿点）右「数据来自果园服务」10px 灰。

**视频区 `.qh-video`**：160px 高、圆角 18px、深底 `linear-gradient(135deg,#2a331e,#1c2318 55%,#151b10)`；左上角半透明黑底小标签（来源 · 模型）；检测框绝对定位 `border:1.5px solid var(--detect-box)` + 同色底标签（9px 墨绿字）；扫描线 `qh-scanline` 1.5px 荧绿渐变 4s 循环。

**按钮家族 `.qh-btn`**（flex 居中、44px 高、圆角 13px、14px 字 500）：
- `--primary`：brand-700 底 + 白字 #f5f7ec + 字距 2px + shadow-btn；按压 brand-800 + scale(.985)。
- `--secondary`：白底 + line-strong 描边 + ink-700 字，36px 高、12px 字、宽随内容。
- `--sm`：40px；`--half`：flex:1 用于并排（取消/确认）；`--ghost-danger`：白底描边 + ink-600 字（危险操作）。
- 文字带内联 SVG 时 SVG 用 #F5F7EC。

**统计卡 `.qh-stats > .qh-stat`**：三等分白卡（圆角 12px、10px 内距），大数字 `--font-num` 20px/600（告警数用 `--warn-fg` 橙），下标签 9px 灰。

**告警卡 `.qh-card .qh-alarmcard`**（圆角 14px）：左 44×44 抓拍缩略图（圆角 6px）+ 标题行「发现 N 只 {物种}」+ 状态徽标 + 位置/时间行 + 底部「录像 0.5 秒 · 置信度 68%」与右侧「查看并处理 ›」链接（brand-500）。

**设备条 `.qh-devicebar`**：sunken 底圆角 12px，图标容器 + 名称 + 「模拟设备 · 人工确认后执行」。

**胶囊 `.qh-pill`**：白底胶囊 20px，绿点 + 「在线」success 字；离线时换 warn 色。

**分段选择 `.qh-seg` / 选项 `.qh-duropt` / 单选 `.qh-radio`**：sunken 槽内选中块圆角 9px；时长三等分 44px 高选项，选中 brand-700 底白字；设置单选卡为白底描边行 + 右侧描述。

**输入 `.qh-input`**：48px 高、白底、line-strong 描边、圆角 12px；聚焦 `border-color:var(--line-focus)` + `box-shadow:var(--shadow-focus)`；错误态 `--danger-stroke` 描边。表单标签 `.qh-formlabel` 11px 灰、字距 1px。

**弹窗体系**：遮罩 `.qh-mask { background:var(--surface-mask) }`（墨绿半透明，**不要纯黑**）；底部抽屉 `.qh-sheet`（上圆角 20px、20px 内距、slideUp 320ms）；居中对话框 `.qh-dialog`（20px 圆角、fadeUp）；确认信息格 `.qh-confinfo`（muted 底圆角 12px，行式 label/value）；按钮行 `.qh-btnrow` 两枚 `--half`（左 ghost-danger 取消、右 primary 确认）；底部 `.qh-confnote` 9px 灰。

**时间线 `.qh-tl`**：左圆点（confirm 沙色 / running 墨绿）+ 标题 + 时间 + 消息，14px 间距。

**底部导航 `.qh-tabbar`**：白底、上描边、78px 高（含底部安全区 padding）；四个 `.qh-tab`（10px 字、字距 1px、图标 20px），选中态：**brand-700 墨绿胶囊（border-radius:27px）+ 白色图标文字**，未选中 ink-400。

**小件**：`.qh-chip`（sunken 底 6px 圆角 9px 字 brand-500）、`.qh-linkstrip`（warn 底关联条）、`.qh-progress`（4px 条）、`.qh-note`（居中 10px 极灰免责）、`.qh-shortcut`（13px 图标 + 文字的次操作）、`.qh-detailimg`（170px 高抓拍大图，绿灰渐变兜底）。

### 七、3D 大屏 HUD（scene/，与 H5 同 token 体系、深色化）

- 页底 `#10160e`；3D 画布全屏（Three.js + OrbitControls，`--use-angle=swiftshader` 才能截图）。
- 顶部/底部用**墨绿黑渐变压边**（rgba(16,22,14,.72)→transparent）。
- 玻璃拟态卡片：`rgba(251,250,243,.94)` 白纸卡 + backdrop-blur(10px) + shadow-md；深色徽标 `rgba(35,43,29,.55)` + blur(8px)。
- 品牌名用宋体白字 + 「3D」荧绿小徽标；状态徽标同 H5 语义。
- 荧绿 `#d3e856`：检测框、扫描幕布、扩散圆环、采样点、指示灯；琥珀 `#e0a03a`：告警标记；橙红 `#ff6a3d/#ffb066`：红外发射环与波束。
- 后期辉光：`UnrealBloomPass(strength .9, radius .45, threshold .78)`——只有荧绿级别亮度泛光。
- 底部操作按钮 `.hud-action`：深色玻璃胶囊（rgba(35,43,29,.6) + blur），主操作「声波驱离」用告警橙底；反馈条 `.repel-msg`（荧绿玻璃底，失败时橙 warn）。
- 设备面板：声学驱鸟器 01 + 红外驱鸟器 02 两行 + 「待驱离鸟群 剩 N 只」行。

### 八、视觉自查清单（生成后逐项核对）

1. 页面底是暖纸 #f3f1e7，卡片纯白带 #e9e6d7 描边——不是灰白、不是深色主题。
2. 墨绿只出现在：主按钮、选中态、「正在监测」、导航胶囊、3D 视角按钮——数一数不超过这五处。
3. 页面大标题是宋体 25px；统计大数字是 Inter；正文 12-13px 无衬线。
4. 所有可点元素高度 ≥44px（次按钮 36px 的 `--secondary` 除外，它总是与图标按钮并排）。
5. 弹窗遮罩是墨绿半透明而非黑色。
6. 视频画面里唯一亮色是 #d3e856。
7. 免责小字出现在控制页与确认弹窗（「模拟执行器 · 不会控制真实硬件」）。
8. 状态徽标颜色严格按第八节映射，不允许自定义新颜色。
