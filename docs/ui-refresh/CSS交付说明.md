# 青禾 UI 重设计 — CSS 交付说明

> 交付物：`design-tokens.css`（变量层）+ `components.css`（组件层）
> 设计稿：Ardot「青禾·果园守护 UI 重设计」（5 页 + Token 板 + 组件状态板 + 4 弹窗）
> 本文件说明新旧 token 对应关系与接入步骤。

---

## 一、接入步骤（3 步）

1. **替换变量层**：用 `design-tokens.css` 整体替换 `current-tokens.css`。
   变量命名沿用旧版风格，组件里 `var(--token)` 引用基本不用改；
   下方「二、改名对照」列出了少数改名的变量。
2. **引入组件层**：在 `App.vue` 全局样式或 `uni.scss` 之后引入 `components.css`，
   新组件直接用 `qh-` 类名；旧组件可以渐进迁移（新旧类名不冲突）。
3. **逐页对照设计稿调整结构**：设计稿在画布上按
   监控 / 告警 / 控制 / 记录 / 登录 + 弹窗 ×4 排布，每一块都标了数据字段。

## 二、改名对照（旧 → 新）

| 旧变量 | 新变量 | 说明 |
| --- | --- | --- |
| `--text-xl: 17px` | `--text-2xl: 18px` / `--text-xl: 15px` | 字号阶梯重排 |
| `--text-3xl~5xl` | `--text-3xl: 24px` / `--text-title: 25px` | 页面标题统一 25px 宋体 |
| `--surface-app` | 并入 `--surface-canvas` | 手机壳底色与画布统一为纸面 |
| `--surface-raised / --surface-muted` | `--surface-raised: #fbfaf3` / `--surface-muted: #f7f5ec` | 取值更新 |
| `--weight-heavy: 750` | 删除 | 中文系统字体无 750，上限 700 |
| 间距 `--space-1~16`（不规则） | `--space-1~10`（4px 基准） | 4/6/8/10/12/14/16/20/24/32 |
| 圆角 `--radius-xs~3xl`（6~30） | `6/9/12/13/14/16/18/20/999` | 与设计稿逐块对应 |
| 阴影 5 档 | 4 档（xs/sm/btn/float/focus） | 全部减淡，去掉 shell 大投影 |

## 三、新增变量（旧版没有）

| 变量 | 值 | 用途 |
| --- | --- | --- |
| `--font-serif` | 思源宋体系统栈 | 页面标题 / 弹窗标题 / 品牌语 |
| `--font-num` | Inter 栈 | 指标数字 / 时间 / 百分比（仪器读数感） |
| `--surface-video` | `#1c2318` | 视频区深底 |
| `--surface-mask` | 墨绿 50% 透明 | 弹窗遮罩（不要改成纯黑） |
| `--detect-box` / `--detect-text` | `#d3e856` / `#22301f` | YOLO 检测框与标签 |
| `--warn-line / --danger-stroke` 等 | — | 语义色补全描边档位 |
| `--touch-min` / `--tabbar-height` | `44px` / `78px` | 触控下限 / 导航高度 |

## 四、组件层能力清单（components.css）

| 类名 | 覆盖内容 |
| --- | --- |
| `.qh-btn--primary/secondary/danger/ghost` + `.is-disabled/.is-loading` | 按钮 4 态 |
| `.qh-input` + `.is-focus/.is-error` + `.qh-input-error` | 输入框 3 态 |
| `.qh-badge--{idle,starting,running,stopping,stopped,ended,interrupted,error}` | 监控任务 8 态（running 实心 + 荧绿呼吸点） |
| `.qh-cmd--{pending,running,completed,failed,cancelled,unknown}` | 指令 6 态 |
| `.qh-alarm--{new,processing,handled,ignored}` | 告警 4 态（复用徽标体系） |
| `.qh-card` + `.qh-card--hover/--active/--sunken` | 卡片 3 态 + 凹陷区 |
| `.qh-stats/.qh-stat` | 指标卡三联 |
| `.qh-video` + `.qh-detect-box/.qh-detect-label/.qh-video__tag` | 视频区 + 检测框叠加 |
| `.qh-progress` | 上传 / 检测进度条 |
| `.qh-seg/.qh-subtabs` | 分段控件 + 二级文字 Tab |
| `.qh-tabbar/.qh-tab/.qh-tab__badge` | 胶囊式底部导航（含安全区适配） |
| `.qh-mask--bottom/--center` + `.qh-sheet/.qh-dialog` | 底部抽屉 / 居中弹窗（入场动画 CSS 原生） |
| `.qh-radio` | 场景切换单选 |
| `.qh-slider` | 参数滑杆 |
| `.qh-tl` | 操作记录时间线（4 种节点色） |
| `.qh-chip/.qh-folder` | 鸟类 chips / 鸟类文件夹行 |
| `.qh-conn` | 连接状态条（正常/重连中/中断三态） |

## 五、设计约束备忘（与需求书 6.1/七 对应）

- 移动端 390×844 基准，页面左右留白 14px，区块间距 9px；
- 主按钮高 46px 且位于内容末尾（拇指热区），所有可点目标 ≥ 44px；
- 「录像演示」「模拟设备」「MVP」三个合规标注保留，样式见 `.qh-video__tag` / 设备条说明；
- 无 backdrop-filter、无多层阴影叠加、动画只用 transform/opacity（低端安卓友好）；
- 图标方案：SVG inline（1.5px 描边、圆角端点），uni-app H5 直接内联，无需图标字体。
