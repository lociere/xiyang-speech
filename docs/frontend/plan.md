# 前端实施计划

> 依据 `spec.md` 的落地步骤。按阶段推进，每阶段可独立验收（见 `validation.md`）。

## 1. 架构总览

```text
浏览器（单页，原生 JS）
   │  仅访问 http://localhost:8000
   ▼
应用层 FastAPI（backend/main.py）
   ├── 托管 frontend/ 静态文件
   ├── /api/* 反代到 worker（httpx）
   └── /api/talk 任务编排（未来，含 mock）
        │
        ├── ASR worker :8101  inference/asr/service.py   /recognize
        ├── TTS worker :8102  inference/tts/service.py   /synthesize
        └── 说话人 worker :8103（未来，第三个独立环境）
```

关键原则：**前端只认 `:8000` 一个源**，所有跨 worker 调用由应用层完成，避免 CORS 与端口暴露。

## 2. 技术选型

| 项 | 决定 | 理由 |
|---|---|---|
| 前端框架 | 无框架，原生 ES modules + 手写 CSS | 符合「无 Node、无前端依赖」既定方向；无 CDN 风险；交互量足够用 |
| 通信 | 原生 `fetch` | 零依赖 |
| 异步任务 | 轮询（1–2s 间隔） | 说话人视频生成场景足够；MVP 不引入 SSE/WebSocket |
| 后端反代 | `httpx` | 已在 `requirements/app.txt` |
| 上传 | `python-multipart` | 已在 `pyproject.toml` |
| mock | 应用层配置开关 | 说话人 worker 未接入时返回示例视频，前端可先联调 |

后续若交互复杂到需要响应式框架，可平滑引入本地 vendored 的 Vue 3（下载 `vue.global.prod.js` 放 `frontend/vendor/`），不动整体架构。

## 3. 目录结构

```text
frontend/
  index.html
  css/app.css
  js/
    main.js        # 标签切换、状态栏、加载态
    api.js         # request() / submitJob() / pollJob()
    asr.js
    tts.js
    talk.js        # 未来
    player.js      # 音频/视频播放与 Blob 下载
backend/
  main.py          # 挂载静态目录 + 汇总路由
  routers/
    __init__.py
    health.py      # /api/health 探测 worker
    asr.py         # 反代 /api/asr/recognize -> :8101
    tts.py         # 反代 /api/tts/synthesize -> :8102
    talk.py        # 未来：job 编排 + mock
```

## 4. 后端改动

### 4.1 静态托管

在 `backend/main.py` 中，路由注册完成后挂载：

```python
from fastapi.staticfiles import StaticFiles

app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
```

`html=True` 让 `/` 直接返回 `index.html`；挂载放在所有 `/api` 路由之后。

### 4.2 汇总健康检查

新增 `backend/routers/health.py`：

- `GET /api/health` 用 `httpx` 以短超时探测 `settings.asr_worker_url`、`settings.tts_worker_url` 及（预留的）`talk_worker_url` 的 `/health` 或根路径，返回 `{"asr": bool, "tts": bool, "talk": bool}`。
- 探测失败不抛异常，只置 `false`，保证前端状态栏永远能渲染。

### 4.3 识别与合成反代

- `backend/routers/asr.py`：`POST /api/asr/recognize` 透传 `audio` 到 `:8101/recognize`，转发响应 JSON。
- `backend/routers/tts.py`：`POST /api/tts/synthesize` 透传 `{"text": ...}` 到 `:8102/synthesize`，转发 `audio/wav` 二进制流（用 `httpx.stream` 转发，保留附件名）。

worker 不可达时返回 502 与明确中文提示。

### 4.4 说话人（预留）

- `backend/routers/talk.py` 提供 `/api/talk`（提交）与 `/api/talk/{job_id}`（查询）。
- 任务状态用进程内字典或文件记录（MVP 足够，不引入队列）；`mock` 开关开启时返回一个占位视频。
- 真正接入后，链路为：`text → 调 TTS worker 生成音频 → 调说话人 worker 生成视频 → 写 video_url`。

## 5. 前端实现要点

- `api.js` 暴露：
  - `request(url, options)`：统一 fetch、错误解析（优先读响应 `detail`）、超时与加载态。
  - `submitJob(payload)`、`pollJob(id, onUpdate)`：提交与轮询，`done/error` 时回调。
- `player.js` 暴露 `playBlob(blob, mime)` 与 `download(blob, filename)`，统一处理音频/视频。
- 各功能模块只负责表单校验、组装请求、渲染结果，不重复实现网络与播放逻辑。
- 状态栏每 10–15s 刷新一次 `/api/health`；手动可刷新。

## 6. 分阶段任务

### 阶段 0：骨架 + 状态栏（先行）

- [ ] 新建 `frontend/index.html`、`css/app.css`、`js/main.js`、`js/api.js`。
- [ ] 三卡布局 + 顶部状态栏 + 标签切换。
- [ ] `backend/main.py` 挂载静态文件。
- [ ] 新增 `backend/routers/health.py` 与 `/api/health`。
- [ ] 前端接入 `/api/health`，状态点渲染。

### 阶段 1：识别 + 合成

- [ ] 新增 `backend/routers/asr.py`、`tts.py` 并注册路由。
- [ ] `js/asr.js`：上传（点击/拖拽）、识别、复制。
- [ ] `js/tts.js`：文本输入（1–300 字校验）、生成、播放、下载。
- [ ] `js/player.js` 播放与下载工具。
- [ ] 与 8101/8102 真实联调，覆盖错误提示。

### 阶段 2：说话人页 + job 抽象

- [ ] `js/talk.js`：图片上传预览、文本输入/复用音频、进度条、视频播放下载。
- [ ] 新增 `backend/routers/talk.py`，先以 mock 返回示例视频。
- [ ] 前端用 mock 打通「提交 → 轮询 → 播放/下载」全链路。

### 阶段 3：接入真实说话人 worker

- [ ] 选定模型（首选 SadTalker，见 `plan.md` 第 7 节），新建 `xiyang-talk` conda 环境并下载权重。
- [ ] 实现 `inference/talk/service.py`，对外提供 `/talk` 与结果查询。
- [ ] 应用层 `/api/talk` 串接 TTS → 说话人，返回真实视频。
- [ ] 全链路验收。

## 7. 说话人（嘴型对齐）技术选型

这是独立于 ASR/TTS 的第三个推理 worker，前端只是其消费者。链路：

```text
图片 + 方言文字 → TTS 生成方言音频（复用 :8102）→ 说话人模型合成口型对齐视频
```

- **首选 SadTalker**：单图 + 音频 → 说话人脸视频，显存约 3–4GB，适配 6GB，文档最全。
- 备选 EchoMimic v2 / Hallo2 / MuseTalk：效果更现代但更吃显存、部署更重。
- Wav2Lip：唇形最准、最轻，但单图模式效果一般。

注意：方言对口型无影响（口型由音频波形驱动），现有方言 TTS 可直接喂给说话人模型。6GB 显存下串行执行，不同时常驻两个模型。

## 8. 风险与对策

| 风险 | 对策 |
|---|---|
| worker 未启动/离线 | `/api/health` 状态灯提前暴露；反代失败返回 502 + 中文提示 |
| 国内网络无法访问 CDN | 前端零 CDN，全部本地静态资源 |
| 说话人模型显存/部署超预期 | 前端先用 mock 打通交互；说话人作为独立 worker 单独排期 |
| TTS 输出较大导致同步请求偏慢 | MVP 全局加载态覆盖；必要时再演进为 job 轮询 |
| 前端零依赖下代码膨胀 | 严格按模块拆分（api/player/asr/tts/talk），复用优先 |
