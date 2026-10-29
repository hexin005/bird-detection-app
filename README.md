# 青禾 · 果园识鸟与远程驱离 MVP

uni-app / Vue 3 / TypeScript / Pinia 移动端，Python / FastAPI / SQLite 后端，复用指定 YOLOv8 权重。真实模型识别预录视频，人工核对告警后调用模拟声学设备，保存关联操作及回执。

当前可运行 H5；Android 应用资源已可编译。APK 打包还需要该项目的 DCloud AppID、签名配置及匹配的 HBuilderX，真机验收尚未完成。

## 本机快速启动

```powershell
npm --prefix mobile ci
npm run build:h5
npm run dev:mvp
```

打开 <http://127.0.0.1:8008>。启动终端会显示本地账号和随机密码；也可在 `.runtime/local.json` 查看。首次启动不会自动检测，登录后点击“开始监测”。

启动脚本优先使用项目 `.venv`，其次使用相邻网页项目现有的 Python 环境。本机已验证后者可以运行指定模型；没有向网页项目环境安装新依赖或修改原项目数据。

默认引用相邻网页项目的 `backend/models/best.pt` 和保留的原始录像 `backend/uploads/6b04f07432584e0f9669344b603d4e07.mp4`。模型与 `train-13bird-focus5-2/weights/best.pt` 哈希一致。源文件保持在原位置，通过 `.runtime/local.json` 的 `model_path`、`video_path` 更换路径，重启服务生效。

## 使用流程

1. 登录，开始监测：加载真实模型，以每秒约 2 帧抽样读取录像。
2. 查看模型标注画面、鸟类及置信度，连续检出后生成告警和抓拍。
3. 打开告警，忽略或“确认并去驱离”；选择 3 / 5 / 8 秒，二次确认执行。
4. 查看待执行、执行中和最终回执；可以停止本次任务。
5. 在巡护记录中查询检测、处理、执行与停止记录，查看关联告警。
6. 通过设置切换正常、离线、超时场景，并调整检测阈值、连续帧数及合并间隔。

后台监测不依赖客户端页面。录像结束后不自动循环，界面提示结束；服务重启不自动恢复监测或重放指令。服务器持久化 SQLite 数据，页面刷新不会把指令标成失败。

## 新环境安装与手机连接

建议 Python 3.10 或 3.11、Node.js 20+。创建独立环境并安装依赖：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r backend/requirements.txt
npm --prefix mobile ci
npm run build:h5
```

提供自己的模型和录像，设置 `BIRD_MODEL_PATH`、`BIRD_VIDEO_PATH`，或在首次初始化生成的 `.runtime/local.json` 中配置路径。数据目录可通过 `BIRD_DATA_DIR` 指定，推理设备可通过 `BIRD_DEVICE` 指定（默认 CPU）。

手机访问局域网服务时：

```powershell
.\scripts\start-mvp.ps1 -ListenAddress 0.0.0.0
```

手机与电脑网络互通后，在浏览器或 App 登录页填入 `http://电脑局域网IP:8008`。默认本机启动只绑定 `127.0.0.1`。本版本用于本地/受信任局域网演示，公网部署需要配置 HTTPS 和访问入口。

账号密码初始化后哈希存入数据库；修改 `local.json` 中的密码不会自动修改已创建的账号。该文件包含本机凭据，不提交 Git、不随源码分享。

## 开发与验证

```powershell
npm run dev:h5       # H5 开发服务 5178，API 代理到 8008
npm run typecheck
npm run build:h5
npm run build:app    # 输出 uni-app Android 应用资源，不生成 APK
.venv\Scripts\python -m unittest discover -s backend/tests -v
npm test            # 原交互 Demo 的回归测试
```

如本机使用相邻网页项目 Python 环境，将 `.venv\Scripts\python` 替换为其解释器路径。真实推理集成测试默认跳过，可显式运行：

```powershell
$env:BIRD_INTEGRATION = '1'
$env:BIRD_TEST_VIDEO = '你的短时有鸟录像.mp4'
.venv\Scripts\python -m unittest discover -s backend/tests -p test_inference.py -v
```

该测试使用真实 YOLO 权重，验证有鸟告警、抓拍、指令关联和空白视频不产生告警；视频应能在 60 秒内完成检测，且确实包含模型可连续识别的鸟。

## 项目结构与说明

- `mobile/`：uni-app 正式移动端；`dist/build/h5` 为 H5 构建，`dist/build/app` 为 App 资源。
- `backend/`：接口、认证、模型任务、模拟执行器、SQLite 存储及测试。
- `.runtime/`：本机配置、数据库、抓拍及模型运行配置（已忽略）。
- `demo/`：保留最初的纯模拟交互原型，`npm run dev` 在 4178 启动。
- [产品设计文档](docs/产品设计文档-MVP.md)、[技术方案](docs/技术方案-MVP.md)：产品与技术范围。
- [MVP 实现与验收](docs/MVP实现与验收.md)：当前实现、已验证内容及 Android 后续步骤。

监控画面为连续 JPEG 检测帧，不是完整帧率的视频流；实际速度取决于机器性能。识别输出不等于正确分类，需人工核对；模拟执行完成不代表实际驱鸟效果。素材中鸟类消失与模拟指令没有因果关系。
