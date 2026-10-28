# 首次安装：从 GitHub 到可运行项目

适用 Linux x86_64（Ubuntu 24.04），或 Windows + WSL2 Ubuntu 24.04。以下命令在 Linux/WSL 终端的仓库根目录执行。Windows 原生 Python、ARM 和其他 CUDA 组合不在此安装配置内。

依次完成系统准备、环境创建、依赖安装、资源下载和本机配置。日常运行见 [running.md](running.md)。

## 1. 准备系统

- Windows/WSL 安装支持当前 PyTorch cu128 runtime 的 Windows NVIDIA 驱动；不要在 WSL 安装 Linux 显卡驱动。
- 原生 Linux 安装匹配的 NVIDIA 驱动，确认 `nvidia-smi` 正常。
- 安装 Linux 版 [Miniforge](https://github.com/conda-forge/miniforge)，新终端确认 `conda --version`。已有可用 Conda 可以继续使用。
- 项目以 12 GB 以上显存、32 GB 内存、8 核 CPU、80 GB 以上可用磁盘作为规划起点，按目标输入验证。按需调度只同时驻留一个模型，容量按最重单模型的推理峰值计算。

```bash
sudo apt update
sudo apt install -y git git-lfs curl ffmpeg sox libsox-dev libsndfile1 build-essential cmake
git lfs install
nvidia-smi
conda --version
```

四套环境分别使用 cu128 / cu121 / cu118。CUDA 运行库由匹配的 PyTorch wheel 依赖提供，当前推理流程不要求额外安装完整 CUDA Toolkit。不要跨环境复制动态库。

环境文件使用 conda-forge 渠道。

## 2. 拉取项目

```bash
git clone --recurse-submodules https://github.com/lociere/xiyang-speech.git
cd xiyang-speech
git submodule update --init --recursive
```

子模块提交由主仓库固定。使用配套依赖清单安装，保持源码、依赖和模型版本一致。模型权重需单独下载。

## 3. 创建四个基础环境

```bash
conda env create -f environments/app.yml
conda env create -f environments/asr.yml
conda env create -f environments/tts.yml
conda env create -f environments/talk.yml
```

YAML 定义 Python 3.10.22、pip、构建工具和环境名。项目依赖安装在对应环境中；已有同名环境时先用 `conda env list` 核对。

## 4. 批量安装依赖

按以下顺序安装，每个环境的 `pip check` 应通过。

### 应用环境

```bash
conda activate xiyang-app
python -m pip install -r requirements/app.txt
python -m pip install --no-deps --no-build-isolation -e .
python -m pip check
```

可编辑安装提供 `xiyang-speech` 命令。前端由应用托管，无需单独安装 Node.js。应用清单包含 pytest 和 Ruff。

### ASR

```bash
conda activate xiyang-asr
python -m pip install -r requirements/asr-cuda.txt -c requirements/asr.txt
python -m pip install -r requirements/asr.txt --build-constraint requirements/build-constraints.txt
python -m pip check
```

### TTS

```bash
conda activate xiyang-tts
python -m pip install -r requirements/tts-cuda.txt -c requirements/tts.txt
python -m pip install -r requirements/tts.txt --build-constraint requirements/build-constraints.txt
python -m pip check
```

`*-cuda.txt` 使用官方 Linux CPython 3.10 GPU wheel 直链和 SHA256；`-c` 同时用完整清单约束其依赖版本，避免第一阶段临时装入不匹配的 NumPy/OpenCV 等包。TTS 的 ORT 1.18 存在同版本不同 CUDA 构建，清单固定微软 CUDA12 构建，不能用默认 PyPI 同版本替代。

构建约束固定隔离构建使用的 setuptools/NumPy，供 whisper 等源码包构建使用。

### 数字人

```bash
conda activate MuseTalk
python -m pip install -r requirements/talk-cuda.txt -c requirements/talk.txt
python -m pip install -r requirements/talk-build.txt
python -m pip install --no-build-isolation --no-deps chumpy==0.70
python -m pip install -r requirements/talk.txt
python -m pip check
python -c "from mmcv.ops import nms; import torch; print(torch.__version__, torch.cuda.is_available())"
```

chumpy 构建依赖已安装的 NumPy、SciPy 和 Cython。MMCV 使用与 Torch 2.0/cu118 匹配的预编译 wheel。

## 5. 准备模型和资源

按 [models.md](models.md) 下载固定版本的 ASR、TTS、MuseTalk、WeText 和人脸检测资源。已有资源校验通过后可复用。

不要把模型权重、缓存、输出或本机环境提交到 GitHub。

## 6. 本机配置与参考录音

```bash
cp -n .env.example .env
```

已有 .env 会保留。按实际部署位置编辑；默认路径与 models.md 一致。配置优先级为进程环境变量 > .env > 默认值，相对路径以仓库为基准。

四环境位于同一个 Conda 的 envs 目录时，启动入口自动查找对应 Python。如果放在不同位置，填写模板中的三个 worker Python 绝对路径。

TTS 使用 `XIYANG_REFERENCE_AUDIO` 的录音。请准备一段有授权、清晰、单人、无背景音乐的录音，建议 5–15 秒，不能超过上游 tokenizer 的 30 秒限制。常用转换方式：

```bash
mkdir -p data
ffmpeg -i 你的参考录音.m4a -ac 1 -ar 24000 -c:a pcm_s16le data/xiyang_prompt.wav
```

`data/xiyang_prompt.wav` 若已有且确认可用，可以复用。录音由使用者或交付方提供。默认风格提示和参考音色只能提供近似口音，昔阳话效果由母语者试听验收。

## 7. 校验并首次使用

```bash
conda activate xiyang-app
python -m inference.verify_models
python -m pytest -q
ruff check backend inference tests
xiyang-speech check
xiyang-speech start
```

检查应在项目未启动时执行，避免端口占用检查误报。打开 http://localhost:8000/，依次测试录音识别、文字合成、照片+录音和照片+文字。

启动后模型待命属于正常状态，收到任务后再加载；启动过程不会安装依赖或下载资源。目标设备的效果和容量验收见 [delivery.md](delivery.md)。

## 排错与更新

- 下载中断：重试对应的 pip/Git LFS/Hugging Face 命令；校验失败时只重新获取受影响资源。
- Hugging Face 连接失败：先处理网络连接或按官方下载文件清单转移资源，不关闭证书验证。
- 同名环境已存在：核对版本后复用，或单独重建对应环境。
- Miniconda 提示渠道条款：按其提示处理对应渠道，或使用 Miniforge。
- 更新代码后：先同步子模块；只有对应清单变化时才安装该环境，模型版本变化时才下载对应模型。
- 不要通过全局 pip、全局 CUDA 路径或安装上游全部依赖来修补某一个环境。
