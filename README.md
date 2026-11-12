# 青禾 · 果园识鸟与远程驱离 MVP

基于 **YOLOv8 + 物联网** 的果园精准驱鸟系统软件原型。移动端采用 uni-app / Vue 3 / TypeScript / Pinia，后端采用 Python / FastAPI / SQLite，复用团队训练好的 YOLOv8 权重，对预录视频进行真实鸟类识别，人工核对告警后调用模拟声学驱鸟设备，并把检测、告警、处理、执行记录持久化保存。

当前状态：

- ✅ 可运行的 H5 网页端（浏览器直接使用）
- ✅ Android 应用资源可编译（`mobile/dist/build/app`），APK 打包需配置 DCloud AppID 与签名
- ✅ 真实 YOLOv8 模型推理 + FFmpeg 视频编码归档
- ⚠️ 驱鸟设备为**模拟执行器**，不控制真实硬件

---

## 一、项目简介

系统按“检测 → 告警 → 人工确认 → 模拟驱离 → 记录归档”的完整流程闭环设计：

```text
预录视频 / 上传视频
        │
        ▼
YOLOv8 目标检测（鸟类别、数量、置信度、位置框）
        │
        ▼
告警规则引擎（置信度阈值 + 连续检出帧数 + 合并间隔）
        │
        ▼
移动端 / H5（画面标注、告警列表、抓拍、鸟类分类）
        │
        ▼
人工确认 → 模拟声学驱离（3/5/8 秒，可停止，可模拟离线/超时）
        │
        ▼
SQLite 持久化 + 视频档案归档（HLS 流式播放 / MP4 合成 / 回看下载）
```

---

## 二、技术栈

| 层次 | 技术 | 说明 |
| --- | --- | --- |
| 移动端 | uni-app + Vue 3 + TypeScript + Pinia | 一套代码输出 H5 与 App 资源 |
| 后端 | Python + FastAPI + Uvicorn | 接口、认证、监控任务、模拟执行器 |
| 模型推理 | Ultralytics YOLOv8 + PyTorch + OpenCV | 真实权重推理，输出检测框与类别 |
| 视频编码 | FFmpeg | H264 / HLS 片段编码，最终合成 MP4 |
| 数据存储 | SQLite（WAL 模式） | 账号、告警、指令、事件、视频档案索引 |
| 通信 | HTTP + WebSocket | HTTP 查询/提交，WebSocket 实时推送状态 |

---

## 三、环境要求（从 0 开始）

在全新电脑上运行本项目，需要先准备好以下软件：

| 软件 | 版本要求 | 用途 | 验证命令 |
| --- | --- | --- | --- |
| Git | 任意较新版本 | 拉取代码 | `git --version` |
| Python | 推荐 **3.10 或 3.11**（实测 3.9 亦可） | 后端运行 | `python --version` |
| Node.js | 推荐 **20+**（实测 22 可） | 前端构建 | `node --version` |
| FFmpeg | 任意较新版本 | 视频编码归档 | `ffmpeg -version` |

> 全部命令默认在 Windows PowerShell 中执行；Linux/macOS 用户只需把路径分隔符与虚拟环境激活命令做对应替换，核心步骤一致。

### 3.1 安装 FFmpeg（Windows 任选其一）

```powershell
# 方式一：winget
winget install --id Gyan.FFmpeg

# 方式二：官网下载后手动加入 PATH
# https://ffmpeg.org/download.html
```

装完重新打开终端，验证：

```powershell
ffmpeg -version
```

> 如果 FFmpeg 装在非 PATH 路径，可在启动后端前用环境变量指定完整路径：
> `$env:BIRD_FFMPEG = 'D:\path\to\ffmpeg.exe'`

---

## 四、从 0 到 1 完整部署步骤

### 第 1 步：拉取代码

```powershell
git clone <仓库地址> bird-detection-app
cd bird-detection-app
```

### 第 2 步：创建 Python 虚拟环境并安装后端依赖

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r backend/requirements.txt
```

> 说明：
> - `requirements.txt` 中 `torch==2.8.0` 在 Windows 上默认安装 CPU 版，可直接用于 CPU 推理（默认 `BIRD_DEVICE=cpu`）。
> - 若需 GPU 推理，请前往 [PyTorch 官网](https://pytorch.org/get-started/locally/) 按本机 CUDA 版本安装对应 wheel，再安装其余依赖。

### 第 3 步：模型与演示视频（已随仓库提供）

模型权重和演示视频**已经放在仓库内 `assets/` 目录**，拉取代码后即存在，**无需手动准备**：

```text
bird-detection-app/
├── assets/
│   ├── best.pt          # YOLOv8 权重（约 6 MB，13 类果园常见鸟类）
│   └── demo-bird.mp4    # 演示视频（约 1.6 MB，30 秒 1080p，含鸟类）
```

两个文件的 SHA-256 校验值（用于确认下载完整）：

```text
C0772AA06C9DE7EDF5A871E5AB980C408FCE823B263F81A140E380E2E155D8DF  best.pt
15D228EF3A0ACDA1878AB1D5AB4F23C4C0E320933A8801946EBC7E740A9A8F65  demo-bird.mp4
```

后端首次启动时会自动把默认模型/视频路径指向 `assets/best.pt` 与 `assets/demo-bird.mp4`，所以**第 4 步通常可以跳过**，直接看第 5 步启动即可。只有在你想换成自己的模型/视频时，才需要第 4 步的配置。

> 如果所在仓库托管平台对单文件大小有限制，可改用 Git LFS 跟踪 `assets/`，见第 4.3 小节。

> **视频格式说明**：`demo-bird.mp4` 为 HEVC/H.265 编码、1920×1080、30fps、30 秒。后端用 OpenCV 解码（支持 HEVC），但如果浏览器直接播放原片遇到兼容问题，改用检测结果归档的 MP4 即可（FFmpeg 统一转码为 H.264）。

### 第 4 步：配置模型与视频路径（仅换模型/视频时需要）

后端通过 `.runtime/local.json` 读取模型与视频路径。`.runtime/` 已被 `.gitignore` 忽略，首次启动会自动生成，默认指向 `assets/best.pt` 和 `assets/demo-bird.mp4`。

**默认情况下无需任何操作**。只有当你需要换用自己的权重或视频时，用下面任一方式覆盖：

**方式 A：直接编辑配置文件**

在项目根目录的 `.runtime/local.json`（首次启动后自动生成）中改路径：

```json
{
  "username": "orchard",
  "password": "你的初始密码",
  "model_path": "D:/your/path/to/your.pt",
  "video_path": "D:/your/path/to/your.mp4"
}
```

**方式 B：环境变量覆盖**

```powershell
$env:BIRD_MODEL_PATH = 'D:\your\path\to\your.pt'
$env:BIRD_VIDEO_PATH = 'D:\your\path\to\your.mp4'
```

> 环境变量优先级高于 `local.json`。首次启动后 `.runtime/local.json` 会被自动创建并写入默认值，之后可随时编辑它并重启服务生效。
>
> **注意**：`password` 只在数据库首次创建时生效。若已运行过、数据库已存在，修改 `local.json` 里的密码不会更新已有账号；需要重置请删除 `.runtime/orchard.sqlite3*` 后重启。

**首次启动会自动生成账号**：用户名固定为 `orchard`，密码为 `local.json` 中的 `password`；若未手动创建 `local.json`，程序会生成随机密码，密码打印在启动终端，也可在 `.runtime/local.json` 中查看。

#### 4.3 大文件进仓库的替代方案（Git LFS）

如果托管的 Git 平台（或学院内部 GitLab）限制单文件大小、导致 64 MB 视频推不上去，用 Git LFS 托管 `assets/` 即可，其他同学/评委拉代码时同样能拿到完整文件：

```powershell
git lfs install
git lfs track "assets/**"
git add .gitattributes assets/
git commit -m "chore: 使用 Git LFS 跟踪模型与演示视频"
git push
```

需要先安装 [Git LFS](https://git-lfs.com/)。`git lfs track` 会生成 `.gitattributes`，里面记录哪些文件走 LFS；提交并推送后，仓库里存的是指针，大文件本体放在 LFS 存储。评审下载时正常 `git clone` 即可自动拉取。

### 第 5 步：安装前端依赖并构建 H5

```powershell
npm --prefix mobile ci
npm run build:h5
```

构建产物输出到 `mobile/dist/build/h5/`。后端启动后会自动挂载该目录，因此**后端服务本身就是完整的网页入口**。

### 第 6 步：启动后端服务

```powershell
npm run dev:mvp
```

等价于执行 `powershell -NoProfile -File scripts/start-mvp.ps1`。启动成功后终端会显示：

```text
Account: orchard
Password: <你的密码>
MVP: http://127.0.0.1:8008
```

### 第 7 步：浏览器访问并登录

打开 **http://127.0.0.1:8008**，输入：

- 服务地址：`http://127.0.0.1:8008`（本机访问时留空或填此地址）
- 账号：`orchard`
- 密码：启动终端显示的密码

登录后点击“选择视频”上传视频，或点击“开始监测”读取 `local.json` 中配置的默认视频（即 `assets/demo-bird.mp4`），即可看到真实模型识别画面。

### 第 8 步：3D 果园场景（可选）

`scene/` 是独立的 Vite + Three.js 前端，**构建产物不在仓库内**，必须单独构建一次，否则 `http://127.0.0.1:8008/scene` 会 404：

```powershell
npm --prefix scene ci
npm --prefix scene run build
```

构建产物 `scene/dist/` 生成后重启后端即可生效（后端启动时检测目录存在才挂载 `/scene`）。不构建不影响主界面任何功能。

---

## 五、（可选）局域网手机访问

手机与电脑连接同一 Wi-Fi，让后端监听局域网地址：

```powershell
.\scripts\start-mvp.ps1 -ListenAddress 0.0.0.0
```

查询电脑局域网 IP：

```powershell
ipconfig   # 找到 IPv4 地址，例如 192.168.1.10
```

手机浏览器打开 `http://192.168.1.10:8008`，在登录页的“服务地址”填入该地址即可。

> 默认 `127.0.0.1` 绑定仅限本机访问，用于本地/受信任局域网演示；公网部署需另行配置 HTTPS 与访问入口。

---

## 六、使用流程

1. **登录**，进入监控页。
2. **选择视频**：上传电脑上的 MP4 / MOV / AVI / MKV / WebM（单文件 ≤ 500 MB），或直接“开始监测”读取默认视频。
3. **开始检测**：后端加载真实 YOLO 权重，按采样帧推理，画面实时标注鸟类别与置信度。
4. **查看告警**：连续检出达到阈值后生成告警与抓拍；可“忽略”或“确认并去驱离”。
5. **执行驱离**：选择 3 / 5 / 8 秒，二次确认后提交至模拟执行器；可随时停止。
6. **查看档案**：记录页按视频/鸟类分类回看，支持播放、拖动进度条、下载结果 MP4。
7. **设置**：切换正常 / 离线 / 超时场景，调整置信度阈值、连续帧数、合并间隔。

后台监测不依赖客户端页面；录像结束后不自动循环；服务重启不自动恢复监测或重放指令。

### 自选鸟类图鉴照片

将照片放进 `.runtime/species/` 下对应鸟种的文件夹，例如 `.runtime/species/八哥/`。每个文件夹放一张 `.jpg`、`.jpeg`、`.png` 或 `.webp` 图片，图片本身可以使用任意文件名。自动创建的 13 个文件夹：八哥、白喉红臀鹎、大嘴乌鸦、树麻雀、黑领椋鸟、丝光椋鸟、红嘴蓝鹊、东方喜鹊、山斑鸠、珠颈斑鸠、栗腹文鸟、花蜜鸟、白领翡翠。此前直接放在 `.runtime/species/八哥.jpg` 这样的图片仍可读取，但同鸟种文件夹内的照片优先。

图鉴封面依次使用自选照片、该鸟种的告警抓拍、默认剪影。替换图片后重新进入图鉴即可刷新；告警抓拍仍保留在 `.runtime/captures/`，不会被自选照片覆盖。

### 鸟类知识库

「我的 → 鸟类知识库」提供 13 种园内鸟种的科普档案与本园记录联动：

- **科普档案**：中英文名、拉丁学名、科属、保护信息（国家“三有”保护动物 / IUCN 受威胁等级，分开呈现）、危害分级、对果园的影响、识别特征、鸣声特点、食性、生态价值、活动时段与本园应对。种子数据在 `backend/knowledge.py`，随代码维护（启动时 UPSERT 对齐，库内手改会在下次启动被覆盖）。
- **本园记录**：每种鸟的累计告警、待处理、最近出现时间、最佳置信度、涉及视频档案数、单帧峰值，以及按历史告警聚合的 24 小时活动时段分布图；卡片封面角标显示本园告警条数。
- **搜索**：按中文名 / 英文名 / 拉丁学名 / 科属即时过滤，忽略大小写与首尾空格。
- **数据来源**：`GET /api/knowledge`（列表）与 `GET /api/knowledge/{name}`（详情），告警聚合与 `/api/library` 同源。接口不可用时页面回落内置静态知识，本园记录显示“暂不可用”而非 0。

### 账号体系（注册 / 找回密码 / 改密）

除首次启动自动创建的 `orchard` 账号外，登录页还支持**邮箱注册、邮箱找回密码、改密码**三条链路。多个账号共享同一个果园数据（告警、指令、视频档案、统计），仅个人资料与界面主题（四套主题）各自独立。

- **注册**：登录页切到「注册」→ 填邮箱 → 点「获取验证码」→ 填 6 位验证码 + 密码（至少 8 位）。注册成功后系统自动派生一个 `user_xxxxxxxxxx` 用户名，也可以用邮箱直接登录。
- **登录标识**：用户名或邮箱都可以作为登录账号，邮箱匹配不区分大小写。
- **找回密码**：登录页「忘记密码」→ 填已绑定邮箱 → 验证码 → 设新密码。未绑定的邮箱会返回「该邮箱未绑定任何账号」。
- **改密码**：登录后「我的 → 账号设置 → 修改密码」，需输入当前密码；改密成功会吊销该账号的全部会话，需重新登录。
- **验证码规则**：10 分钟有效；重发间隔 60 秒；同一验证码连续输错 5 次作废；注册码与重置码互不通用；服务端另有限流（全来源每分钟最多 10 条）。

**验证码投递方式**（二选一，由 `.runtime/local.json` 决定）：

| 场景 | 配置 | 表现 |
| --- | --- | --- |
| 演示模式（默认） | 不配置 `smtp_*` | 验证码打印在后端控制台 `[email-demo] ... 验证码 -> 邮箱: 123456`，同时接口返回 `demo_code`，登录页顶部出现黄色横幅「演示验证码:123456」。**开箱即可注册，无需邮箱服务** |
| 真实邮件 | 配置完整 `smtp_*` | 走 SMTP 真发（465 端口 SSL，587 端口 STARTTLS）。**发送失败一律返回 502 报错，绝不回退成演示码**，避免"SMTP 配错"被误解成验证码公开 |

SMTP 与演示开关的可选字段（写进 `.runtime/local.json`，均可留空）：

```json
{
  "smtp_host": "smtp.qq.com",
  "smtp_port": 465,
  "smtp_user": "你的发件邮箱",
  "smtp_pass": "邮箱授权码（非登录密码）",
  "smtp_from": "你的发件邮箱",
  "email_demo": false
}
```

> - `email_demo` 缺省为 `true`；设为 `false` 且 `smtp_host` 为空时，发码接口直接报错，不再打印验证码。
> - 这些字段和 `deepseek_key` 一样只存在本机 `.runtime/local.json`，**不入库、不入 git**。
> - 验证码保存在进程内存中，**后端重启后已发出的验证码全部失效**，需重新获取；多 worker 部署需换共享存储（当前 MVP 单进程，不涉及）。

### AI 助手（DeepSeek 问答）

首页右缘有「AI 助手」悬浮小按钮：点击弹出聊天小窗，点 ■ 最大化成整页视图，点 — 缩回按钮；三种状态间会话与未发送草稿均保留（页面刷新后清空）。

- **问答策略（RAG 优先）**：问题先经本地检索——明确鸟种（名称/学名/别名，别名一对多映射）、本园统计（意图词 + 按时间范围取数，附口径说明：告警次数≠鸟类个体数）、非特定鸟种知识（对知识卡字段做关键词匹配）；命中内容作为“参考资料”注入 DeepSeek 整理作答，前端展示可点击的参考资料标签（跳知识卡/数据分析）；未命中则标注“AI 通用回答 · 未引用本园知识库”。
- **只读边界**：AI 不连接驱鸟设备接口，不能执行任何驱离操作；涉及操作时引导用户在应用内人工处理。
- **接口**：`GET /api/assistant/status`（配置状态）、`POST /api/assistant/chat`（SSE 流式：meta→delta*→done）；同一时刻仅允许一条回答在生成（409 防重复提交）。
- **配置 DeepSeek**（不配置时界面显示引导、发送禁用）：在 `.runtime/local.json` 增加：

```json
{
  "deepseek_key": "sk-你的密钥",
  "deepseek_model": "deepseek-chat",
  "deepseek_base_url": "https://api.deepseek.com"
}
```

  或设置环境变量 `BIRD_DEEPSEEK_KEY` 后重启后端。key 只存本机，不入库不入 git。

> **AI 助手需自备外部 Key**：仓库内不含任何 `sk-` 密钥，`.runtime/local.json` 也不随仓库分发。组委会拉取代码后若要用 AI 助手，需自行准备一个 DeepSeek（或任意 OpenAI 兼容服务）的 Key 填入上面的字段；**不配置不影响其他任何功能**——`GET /api/assistant/status` 返回 `configured: false`，前端显示配置引导并禁用发送，检测、告警、驱离、档案、知识库、数据分析全部照常可用。
>
> `deepseek_base_url` 可指向任何 OpenAI 兼容端点（自建 Ollama / vLLM / 其它厂商网关均可），只需实现 `POST {base_url}/chat/completions` 的 SSE 流式格式。

---

## 七、开发与验证

```powershell
npm run dev:h5       # H5 开发服务 5178，API 代理到 8008
npm run typecheck    # TypeScript 类型检查
npm run build:h5     # H5 生产构建（输出 mobile/dist/build/h5）
npm run build:app    # uni-app Android 应用资源（非 APK）

npm --prefix scene run build   # 3D 果园场景构建（输出 scene/dist，可选）

# 后端单元测试（41 项：认证/会话、告警合并、并发幂等、离线/超时/停止、重启恢复、
# 注册验证码与改密吊销、账号隔离、自动化规则与定时巡逻、数据分析口径等）
.venv\Scripts\python -m unittest discover -s backend/tests -p test_backend.py -v

# 配置加载测试（local.json 升级合并、可选字段补齐、env 优先级，3 项）
.venv\Scripts\python -m unittest discover -s backend/tests -p test_config.py -v

# 视频档案/媒体授权测试（14 项）
.venv\Scripts\python -m unittest discover -s backend/tests -p test_video_library.py -v

# 鸟类知识库测试（种子 UPSERT、聚合口径、边界与鉴权，8 项）
.venv\Scripts\python -m unittest discover -s backend/tests -p test_knowledge.py -v

# AI 助手测试（检索三分类、流式事件序、上游故障剧本、在飞锁，17 项）
.venv\Scripts\python -m unittest discover -s backend/tests -p test_assistant.py -v

# 原交互 Demo 回归测试
npm test
```

> 后端单元测试合计 **83 项**（41 + 14 + 8 + 17 + 3），另有两项真实模型集成测试默认跳过（下方）。

真实模型 + FFmpeg 集成测试默认跳过，可显式运行（需要真实权重和一段有鸟短片）：

```powershell
$env:BIRD_INTEGRATION = '1'
$env:BIRD_TEST_VIDEO = '你的短时有鸟录像.mp4'
.venv\Scripts\python -m unittest discover -s backend/tests -p test_inference.py -v
.venv\Scripts\python -m unittest discover -s backend/tests -p test_video_pipeline.py -v
```

---

## 八、常见问题（FAQ）

**Q1：启动时报“模型或视频不存在”？**
检查 `.runtime/local.json` 的 `model_path`、`video_path` 是否指向真实文件；或设置 `BIRD_MODEL_PATH` / `BIRD_VIDEO_PATH` 环境变量后重启。默认情况下应指向仓库内的 `assets/best.pt` 和 `assets/demo-bird.mp4`。

**Q2：登录提示“账号或密码错误”？**
首次启动会创建账号。若改了 `local.json` 的密码但数据库已存在，旧密码不会自动更新；删除 `.runtime/orchard.sqlite3*` 后重启，会按 `local.json` 重新初始化。

**Q3：上传视频后无法生成播放视频，提示“服务器缺少 FFmpeg”？**
安装 FFmpeg 并加入 PATH，或用 `$env:BIRD_FFMPEG` 指定完整路径。

**Q4：推理很慢？**
默认 CPU 推理，速度取决于机器与视频分辨率。可在 `.runtime/local.json` 或环境变量 `BIRD_DEVICE` 指定推理设备（如 `cuda:0`），并确认已安装对应 GPU 版 PyTorch。

**Q5：`.runtime/` 为什么看不到？**
它是本机运行时目录，已被 Git 忽略，不会随仓库提交。凭据、数据库、抓拍、视频档案都在这里，**不要提交或分享其中的 `local.json`**。

**Q6：首次启动终端没打印账号密码？**
只有走 `npm run dev:mvp`（即 `scripts/start-mvp.ps1`）才会在控制台打印 `Account / Password`。如果直接用 `uvicorn backend.main:create_app --factory` 启动，凭据不会打印，请打开 `.runtime/local.json` 查看 `username` 与 `password` 字段。

**Q7：注册时收不到验证码邮件？**
默认是演示模式：不配 SMTP 时验证码不真正发信，而是①打印在后端控制台 `[email-demo] 注册 验证码 -> ...`；②登录页顶部显示「演示验证码:xxxxxx」横幅。若要真发邮件，按第六节「账号体系」配置 `smtp_host / smtp_port / smtp_user / smtp_pass / smtp_from` 并把 `email_demo` 设为 `false` 后重启。注意服务端重启会清空内存中已发出的验证码。

**Q8：`http://127.0.0.1:8008/scene` 打不开（404）？**
3D 场景的构建产物不入库，需先执行 `npm --prefix scene ci && npm --prefix scene run build` 生成 `scene/dist/`，再重启后端。主界面不受影响。

---

## 九、项目结构与说明

```text
bird-detection-app/
├── assets/                 # 模型权重 best.pt 与演示视频 demo-bird.mp4（随仓库提交）
├── mobile/                 # uni-app 移动端（Vue 3 + TS + Pinia）
│   ├── src/                # 页面、组件（含 host/ 四主题外壳、theme-pages/）、状态管理
│   └── dist/build/         # H5 与 App 构建产物（已忽略，需自行构建）
├── scene/                  # 3D 低多边形果园场景（Vite + Three.js，独立构建）
│   └── dist/               # 场景构建产物（已忽略，构建后由后端挂载到 /scene）
├── backend/                # FastAPI 后端
│   ├── main.py             # 接口、认证、WebSocket、静态挂载
│   ├── config.py           # 配置加载（local.json / 环境变量）与升级合并
│   ├── detector.py         # YOLO 推理、标注、告警门控
│   ├── video_pipeline.py   # FFmpeg HLS 编码 + MP4 合成管线
│   ├── video_library.py    # 视频档案与鸟类索引
│   ├── knowledge.py        # 鸟类知识库种子数据（代码即权威版本）
│   ├── assistant.py        # AI 助手：本地检索三分类 + DeepSeek 流式问答（只读）
│   ├── security.py         # 口令哈希（PBKDF2）、会话摘要、媒体票据
│   ├── verification.py     # 注册/找回验证码：签发、校验、频控（进程内存）
│   ├── emailer.py          # 验证码邮件投递（SMTP 真发 / 演示模式）
│   ├── store.py            # SQLite 存储、事务、模拟执行器
│   └── tests/              # 后端单元/集成测试
├── scripts/
│   ├── start-mvp.ps1       # 后端启动脚本（打印账号密码）
│   └── serve.mjs           # 原始 Demo 静态服务
├── demo/                   # 最初的纯前端模拟原型
├── docs/                   # 产品、技术、验收文档与 UI 设计稿
├── tests/                  # Demo 回归测试
└── .runtime/               # 本机配置/数据库/抓拍/档案（已忽略，首次启动自动生成）
```

相关文档：

- [产品设计文档-MVP](docs/产品设计文档-MVP.md)
- [技术方案-MVP](docs/技术方案-MVP.md)
- [MVP 实现与验收](docs/MVP实现与验收.md)
- [H5 视频检测与分类改进](docs/H5视频检测与分类改进.md)
- [UI 风格提示词](docs/UI风格提示词.md)
- [青禾·果园守护 UI 重设计（PDF）](docs/青禾·果园守护%20UI%20重设计.pdf)
- [UI 重设计需求书](docs/ui-refresh/UI重设计需求书.md) / [CSS 交付说明](docs/ui-refresh/CSS交付说明.md)（含 `screens/` 六张页面设计图与 `h5-preview.html` 预览）

> `docs/` 下另有若干以 `ui-*` 命名的设计过程目录（`ui-flow`、`ui-rc`、`ui-v3`、`ui-w`、`ui-x`、`ui-y`、`ui-z`、`ui-signal-redesign`、`ui-scene-hud`、`ui-scene-tech`、`scene-farm` 等），它们是各轮界面迭代的静态预览稿与截图，**仅供设计追溯，不参与构建、不被后端服务**。

---

## 十、重要说明

- 监控画面为连续标注 JPEG 检测帧 / HLS 流式编码，实际速度取决于机器性能。
- **识别输出不等于正确分类**，需人工核对；模拟执行完成不代表实际驱鸟效果。
- 素材中鸟类消失与模拟指令没有因果关系。
- 本项目为**软件原型（MVP）**，真实硬件控制、自动驱离、云边协同、边缘端轻量化部署属于申报书中的后续研究内容，未在本版本实现。
