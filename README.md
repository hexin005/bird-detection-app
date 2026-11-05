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
│   └── demo-bird.mp4    # 演示视频（约 64 MB，含鸟类，可跑通完整流程）
```

两个文件的 SHA-256 校验值（用于确认下载完整）：

```text
C0772AA06C9DE7EDF5A871E5AB980C408FCE823B263F81A140E380E2E155D8DF  best.pt
77D980C525823E7168480735DCD9014586FF8D43D9CC4037905641D8038B9441  demo-bird.mp4
```

后端首次启动时会自动把默认模型/视频路径指向 `assets/best.pt` 与 `assets/demo-bird.mp4`，所以**第 4 步通常可以跳过**，直接看第 5 步启动即可。只有在你想换成自己的模型/视频时，才需要第 4 步的配置。

> 如果所在仓库托管平台对单文件大小有限制，可改用 Git LFS 跟踪 `assets/`，见第 4.3 小节。

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

---

## 七、开发与验证

```powershell
npm run dev:h5       # H5 开发服务 5178，API 代理到 8008
npm run typecheck    # TypeScript 类型检查
npm run build:h5     # H5 生产构建
npm run build:app    # uni-app Android 应用资源（非 APK）

# 后端单元测试（12 项：认证、告警合并、并发幂等、离线/超时/停止、重启恢复等）
.venv\Scripts\python -m unittest discover -s backend/tests -p test_backend.py -v

# 视频档案/媒体授权测试
.venv\Scripts\python -m unittest discover -s backend/tests -p test_video_library.py -v

# 原交互 Demo 回归测试
npm test
```

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

---

## 九、项目结构与说明

```text
bird-detection-app/
├── assets/                 # 模型权重 best.pt 与演示视频 demo-bird.mp4（随仓库提交）
├── mobile/                 # uni-app 移动端（Vue 3 + TS + Pinia）
│   ├── src/                # 页面、组件、状态管理
│   └── dist/build/         # H5 与 App 构建产物（已忽略）
├── backend/                # FastAPI 后端
│   ├── main.py             # 接口、认证、WebSocket、静态挂载
│   ├── config.py           # 配置加载（local.json / 环境变量）
│   ├── detector.py         # YOLO 推理、标注、告警门控
│   ├── video_pipeline.py   # FFmpeg HLS 编码 + MP4 合成管线
│   ├── video_library.py    # 视频档案与鸟类索引
│   ├── store.py            # SQLite 存储、事务、模拟执行器
│   └── tests/              # 后端单元/集成测试
├── scripts/
│   ├── start-mvp.ps1       # 后端启动脚本
│   └── serve.mjs           # 原始 Demo 静态服务
├── demo/                   # 最初的纯前端模拟原型
├── docs/                   # 产品、技术、验收文档
├── tests/                  # Demo 回归测试
└── .runtime/               # 本机配置/数据库/抓拍/档案（已忽略）
```

相关文档：

- [产品设计文档-MVP](docs/产品设计文档-MVP.md)
- [技术方案-MVP](docs/技术方案-MVP.md)
- [MVP 实现与验收](docs/MVP实现与验收.md)
- [H5 视频检测与分类改进](docs/H5视频检测与分类改进.md)

---

## 十、重要说明

- 监控画面为连续标注 JPEG 检测帧 / HLS 流式编码，实际速度取决于机器性能。
- **识别输出不等于正确分类**，需人工核对；模拟执行完成不代表实际驱鸟效果。
- 素材中鸟类消失与模拟指令没有因果关系。
- 本项目为**软件原型（MVP）**，真实硬件控制、自动驱离、云边协同、边缘端轻量化部署属于申报书中的后续研究内容，未在本版本实现。
