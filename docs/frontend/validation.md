# 前端验收清单

> 对应 `spec.md` 的功能需求与 `plan.md` 的阶段。分「自动化」「接口」「浏览器手工」三层。

## 1. 自动化工程检查

在 `xiyang-app` 环境执行，须全部通过：

```bash
conda activate xiyang-app
python -m pytest -q
ruff check backend inference tests
```

新增的后端路由应有对应单元测试（用 `fastapi.testclient.TestClient` + 对 worker 的 mock 响应），至少覆盖：

- `/api/health` 在 worker 离线时返回 `{"asr": false, ...}` 且不抛异常。
- `/api/asr/recognize`、`/api/tts/synthesize` 的请求校验与 worker 不可达时的 502。

## 2. 启动与准备

依次启动三个进程（说话人 worker 本阶段可不启动）：

```bash
# ASR worker
conda activate xiyang-asr
python -m uvicorn inference.asr.service:app --host 127.0.0.1 --port 8101

# TTS worker（注意动态库路径，见 docs/installation.md）
conda activate xiyang-tts
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib/python3.10/site-packages/torch/lib:$CONDA_PREFIX/lib/python3.10/site-packages/nvidia/cudnn/lib:$CONDA_PREFIX/lib/python3.10/site-packages/nvidia/cublas/lib:$CONDA_PREFIX/lib/python3.10/site-packages/nvidia/cuda_runtime/lib:${LD_LIBRARY_PATH:-}"
python -m uvicorn inference.tts.service:app --host 127.0.0.1 --port 8102

# 应用层（托管前端）
conda activate xiyang-app
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

浏览器访问 `http://localhost:8000/` 应看到单页界面，`http://localhost:8000/docs` 应列出所有 `/api` 路由。

## 3. 接口验收（curl）

```bash
# 已有健康接口
curl -s http://localhost:8000/health

# 汇总状态（两个 worker 在线时应为 true）
curl -s http://localhost:8000/api/health

# 识别：上传 data/test_1.wav
curl -s -F "audio=@data/test_1.wav" http://localhost:8000/api/asr/recognize

# 合成：返回 wav，写入 runtime/outputs/check_web.wav 试听
curl -s -X POST http://localhost:8000/api/tts/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"今天天气不错，咱们吃完饭出去走走吧。"}' \
  -o runtime/outputs/check_web.wav
```

验收点：

- `/api/health` 在停掉某个 worker 后，对应字段在 15s 内变为 `false`，页面状态点变红。
- 识别返回 `{"text": "..."}` 且文字可读。
- 合成的 `check_web.wav` 可正常播放。

## 4. 浏览器手工验收

### 4.1 状态栏

- [ ] 三个状态点按 worker 实际在线/离线显示绿/红。
- [ ] 停掉一个 worker 后手动刷新，状态点正确变化。

### 4.2 识别

- [ ] 点击上传与拖拽上传均可选择音频文件。
- [ ] 上传合法 `.wav/.mp3/.m4a/.flac` 后识别成功，文字展示正确。
- [ ] 「复制」按钮复制出识别文字，并有成功反馈。
- [ ] 上传非法格式（如 `.txt`）：明确提示不支持。
- [ ] 上传空文件或无声录音：明确提示「未识别出文字」。

### 4.3 合成

- [ ] 输入 1 字可生成；300 字边界可生成。
- [ ] 超过 300 字被前端拦截并提示；空输入被拦截。
- [ ] 生成后音频可播放，「下载」得到 `xiyang_speech.wav`。
- [ ] 合成失败（如停掉 TTS worker）：明确提示而非白屏。

### 4.4 说话人（真实 MuseTalk）

- [ ] 上传图片有预览。
- [ ] 输入文字提交后出现进度条，并最终进入「完成」状态。
- [ ] 完成后视频可播放、可下载。
- [ ] 提交后重复点击「生成」被禁用，避免重复提交。
- [ ] 上传无法检测人脸的图片时展示明确提示。

## 5. 失败场景（与 `docs/delivery.md` 对齐）

- [ ] 无效文件、空输入、超长输入、运行失败均给出明确中文提示。
- [ ] 应用层能访问但某 worker 离线时，操作返回 502 且提示「服务离线/不可用」。
- [ ] 刷新页面不残留半截状态（不依赖 localStorage 的历史数据）。

## 6. 说话人补充验收

真实 worker 已接入，以下在实际部署设备上验收：

- [ ] 上传人物图片 + 输入方言文字，产出视频中人物口型与语音基本对齐。
- [ ] 用「复用合成音频」路径得到同样的对齐效果。
- [ ] 无清晰人脸 / 无人物时给出明确失败提示。
- [ ] 串行链路（TTS → 说话人）在目标设备上稳定运行，无显存溢出。

## 7. 交付门槛

全部满足才算阶段完成：

- 自动化测试与 `ruff` 通过。
- 第 3 节接口验收通过。
- 第 4 节对应阶段的浏览器手工项全部勾选。
- 识别、合成的失败场景（第 5 节）全部通过。
