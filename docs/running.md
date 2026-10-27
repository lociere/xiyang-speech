# 运行说明

> 本文说明如何启动并验证系统。安装环境与下载模型见 [installation.md](installation.md)。
> 当前阶段：识别、合成、图片说话（真实 MuseTalk 口型）均可用。

## 1. 架构：四个进程

系统由四个独立进程组成，分属四个 conda 环境、四个端口：

| 进程 | 代码 | 环境 | 端口 | 作用 |
|---|---|---|---|---|
| 应用层 | `backend/main.py` | xiyang-app | 8000 | 托管前端页面，反代到 worker |
| ASR worker | `inference/asr/service.py` | xiyang-asr | 8101 | 加载 FunASR，做语音识别 |
| TTS worker | `inference/tts/service.py` | xiyang-tts | 8102 | 加载 CosyVoice，做语音合成 |
| Talk worker | `inference/talk/service.py` | MuseTalk | 8103 | 加载 MuseTalk，做图片口型视频 |

浏览器只访问 `:8000`，由应用层转发到 worker，前端不直接访问 worker 端口。

## 2. 前提（一次性准备）

### 2.1 四个 conda 环境已建好

按 [installation.md](installation.md) 完成「应用 / 识别 / 生成」三个环境；MuseTalk 环境按 [musetalk.md](musetalk.md) 建立（torch 2.0.1+cu118、MMLab 的 mmcv/mmdet/mmpose、`requirements/talk.txt`）。模型与 MuseTalk 权重都已下载到 `models/` 和 `third_party/MuseTalk/models/`。

### 2.2 依赖与参考音频

Web 依赖已包含在各自的 `requirements/*.txt` 中，按安装文档安装即可，不必另装最新版。图片加文字使用本地 `data/xiyang_prompt.wav` 作为 TTS 参考音频；图片加已有音频不需要调用 TTS。

## 3. 重要：内存限制（串行运行）

ASR、TTS、MuseTalk 都需要较多内存和显存。资源不足时同时常驻可能触发 OOM（终端显示 `Killed`，退出码 137）；是否能够同时运行以部署设备的实际测试为准。

本地首次验证建议**串行运行**：每个 worker 单独启动，用完停掉再换下一个。

- 图片说话走「图片 + 文字」时，Talk worker 会卸载 MuseTalk 主模型，启动 TTS 子进程，待子进程退出后重新加载 MuseTalk。人脸检测组件仍驻留，因此这不是完全释放所有模型。模型切换会增加等待时间。

## 4. 只跑「合成」（TTS）

**终端 1 — TTS worker（务必先设动态库路径）**

```bash
cd ~/xiyang-speech
conda activate xiyang-tts
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib/python3.10/site-packages/torch/lib:$CONDA_PREFIX/lib/python3.10/site-packages/nvidia/cudnn/lib:$CONDA_PREFIX/lib/python3.10/site-packages/nvidia/cublas/lib:$CONDA_PREFIX/lib/python3.10/site-packages/nvidia/cuda_runtime/lib:${LD_LIBRARY_PATH:-}"
python -m uvicorn inference.tts.service:app --host 127.0.0.1 --port 8102
```

**终端 2 — 应用层**

```bash
cd ~/xiyang-speech
conda activate xiyang-app
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 `http://localhost:8000/`，切到「合成」卡片即可用。

## 5. 只跑「识别」（ASR）

**终端 1 — ASR worker**

```bash
cd ~/xiyang-speech
conda activate xiyang-asr
python -m uvicorn inference.asr.service:app --host 127.0.0.1 --port 8101
```

**终端 2 — 应用层（同上）**

```bash
cd ~/xiyang-speech
conda activate xiyang-app
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

浏览器切到「识别」卡片即可用。

## 6. 只跑「图片说话」（Talk worker + 应用层）

**终端 1 — Talk worker（MuseTalk 环境）**

```bash
cd ~/xiyang-speech
conda activate MuseTalk
python -m uvicorn inference.talk.service:app --host 127.0.0.1 --port 8103
```

> 首个任务会加载 MuseTalk 主模型；文字任务还会额外运行 TTS 并重新加载主模型。耗时取决于设备。只使用图片说话时，无需另开 `:8102` 的 TTS worker。

**终端 2 — 应用层**

```bash
cd ~/xiyang-speech
conda activate xiyang-app
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

浏览器切到「图片说话」卡片，上传人物图片 + 文字（或音频）即可。

图片建议使用清晰、面部无遮挡的单人正脸人像。卡通或非人类角色可能无法检测；人脸检查失败时会提前给出中文提示。奇数尺寸图片会在视频编码时补齐到偶数宽高。当前采用自动人脸定位，尚无手动面部/嘴部选择。

## 7. 验证

等终端出现 `Application startup complete` 后再操作。Talk worker 的完整主模型在首个任务时加载，健康接口在线只表示服务能够接收请求。

```bash
# 应用层健康
curl http://localhost:8000/health

# 汇总状态：对应 worker 在线时应为 true
curl http://localhost:8000/api/health

# 接口文档
# 浏览器打开 http://localhost:8000/docs
```

前端顶部状态栏会实时反映四个服务的在线/离线状态。

## 8. 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 启动时报 `Killed`，退出码 137 | 内存不足，多个模型同时跑触发 OOM | 只跑一个 worker，串行使用 |
| `Could not load library: ...libtorchaudio.so` | TTS 未设动态库路径，或 torch/torchaudio 版本不匹配 | 设 `LD_LIBRARY_PATH`；确认都是 `2.3.1+cu121` |
| `No module named 'gdown'` | TTS 环境缺 gdown | `pip install gdown` |
| `No module named 'uvicorn'` / `fastapi` | worker 环境缺 Web 依赖 | 见第 2.2 节补装 |
| `PreTrainedModel requires PyTorch` | transformers 版本过新（≥5 需 torch≥2.5），与 torch 2.3.1 不匹配 | 确认 `transformers==4.51.3`、`diffusers==0.29.0` |
| `No module named 'inference.tts'` | 从非项目根目录启动，或装了 PyPI 同名包 `inference`（Roboflow） | 在项目根目录运行；`pip uninstall inference` 及 `inference-models` 等 |
| 图片说话报 `No module named 'mmpose'` 等 | MuseTalk 环境 MMLab 依赖缺失 | 按 [MuseTalk 环境](musetalk.md) 安装固定版本与匹配的 MMCV wheel |
| 图片说话报 `no face detected` | 图片里没人脸，或人脸太小/侧脸 | 换一张正脸、清晰的人像 |
| 上传音频/图片无反应 | 前端或应用层未起 | 确认应用层 `:8000` 已启动 |

## 9. 停止

在对应终端按 `Ctrl+C` 即可停止。停止后再切换跑另一个 worker。
