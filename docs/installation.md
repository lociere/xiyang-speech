# 安装与运行

适用：Windows + WSL2 Ubuntu 24.04、NVIDIA GPU、Python 3.10。以下命令都在 WSL 终端执行。已有本机环境可以直接从第 5 步检查，不必重新安装。

## 1. 准备系统

在 Windows 安装 NVIDIA 驱动，确认 WSL 中 `nvidia-smi` 能看到显卡。不在 WSL 另装 Linux 显卡驱动；本基础推理配置不要求完整 CUDA Toolkit。

```bash
sudo apt update
sudo apt install -y git git-lfs ffmpeg sox libsox-dev libsndfile1 build-essential cmake
git lfs install
```

安装 Linux 版 [Miniconda](https://www.anaconda.com/docs/getting-started/miniconda/install) 或 [Miniforge](https://github.com/conda-forge/miniforge)，新开终端后确认 `conda --version` 可用。

## 2. 获取仓库

```bash
git clone --recurse-submodules https://github.com/lociere/xiyang-speech.git
cd xiyang-speech
git submodule update --init --recursive
```

已有仓库直接进入根目录，执行子模块初始化即可。VS Code 用 WSL 模式打开此目录。Git 负责拉取项目和第三方源码；Python 环境与模型权重需要按下文另行安装、下载。

## 3. 安装环境

应用、识别、生成分别安装，避免依赖冲突。同名环境已存在时不要重复创建。

数字人使用第四个独立环境 `MuseTalk`，按 [MuseTalk 环境](musetalk.md) 安装。只使用“图片 + 已有音频”时需要应用和 MuseTalk；“图片 + 文字”还需要 TTS 环境与参考音频。

**应用：**

```bash
conda create -n xiyang-app python=3.10.22 pip --override-channels -c conda-forge
conda activate xiyang-app
python -m pip install -r requirements/app.txt
python -m pip install --no-deps --no-build-isolation -e .
python -m pip check
```

**识别：**

```bash
conda create -n xiyang-asr python=3.10.22 pip --override-channels -c conda-forge
conda activate xiyang-asr
python -m pip install pip==26.2.1 setuptools==80.9.0 wheel==0.48.0
python -m pip install torch==2.9.1+cu128 torchaudio==2.9.1+cu128 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r requirements/asr.txt --build-constraint requirements/build-constraints.txt
python -m pip check
```

**生成：**

```bash
conda create -n xiyang-tts python=3.10.22 pip --override-channels -c conda-forge
conda activate xiyang-tts
python -m pip install pip==26.2.1 setuptools==80.9.0 wheel==0.48.0
python -m pip install torch==2.3.1+cu121 torchaudio==2.3.1+cu121 --index-url https://download.pytorch.org/whl/cu121
python -m pip install --no-deps onnxruntime-gpu==1.18.0 --index-url https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/onnxruntime-cuda-12/pypi/simple/
python -m pip install -r requirements/tts.txt --build-constraint requirements/build-constraints.txt
python -m pip check
```

不要在这两套模型环境里额外安装 DeepSpeed 或替换 CUDA/ORT 版本。依赖文件和特殊安装源按已验证配置保留，普通使用不需要调整 `.in` 或 `pyproject.toml`。

## 4. 下载模型

模型不包含在代码仓库内。已有完整模型时跳过下载，直接校验。以下均在仓库根目录执行，clone 目标目录必须尚不存在。

**ASR：**

```bash
mkdir -p models/asr
GIT_LFS_SKIP_SMUDGE=1 git clone https://www.modelscope.cn/FunAudioLLM/Fun-ASR-Nano-2512.git models/asr/Fun-ASR-Nano-2512
git -C models/asr/Fun-ASR-Nano-2512 checkout --detach 05201c46f1c38592b1567f857c0d56eab3d0d8ef
git -C models/asr/Fun-ASR-Nano-2512 lfs pull
```

**TTS：**

```bash
conda activate xiyang-tts
hf download FunAudioLLM/Fun-CosyVoice3-0.5B-2512 --revision 29e01c4e8d000f4bcd70751be16fa94bf3d85a18 --local-dir models/tts/Fun-CosyVoice3-0.5B-2512 --include 'CosyVoice-BlankEN/*' campplus.onnx configuration.json cosyvoice3.yaml flow.pt hift.pt llm.pt speech_tokenizer_v3.onnx
```

保留这里指定的来源和版本：不同平台上的同名 ASR 模型文件可能不同。随后校验：

```bash
python -m inference.verify_models --component asr
python -m inference.verify_models --component tts
```

预期 ASR 11 个、TTS 13 个必要文件全部通过。MuseTalk 安装后用 `--component talk` 校验 10 个文件；省略参数会检查全部三个模型组件。

## 5. 配置与检查

首次配置复制模板；已有 `.env` 时直接编辑，避免覆盖本地路径：

```bash
cp .env.example .env
```

默认路径已对应上述下载目录。`.env` 由应用层读取，可配置 worker 地址；独立 worker 当前使用源码中约定的仓库内模型路径，修改 `.env` 不会自动改变这些路径。建议保持上述目录。检查命令需要使用外部目录时，另传 `--model-dir`。

检查识别：

```bash
conda activate xiyang-asr
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
python -m inference.asr.check
```

应显示 `2.9.1+cu128 True`，识别结果在 `runtime/checks/asr.json`。

等识别进程退出，再检查生成：

```bash
conda activate xiyang-tts
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib/python3.10/site-packages/torch/lib:$CONDA_PREFIX/lib/python3.10/site-packages/nvidia/cudnn/lib:$CONDA_PREFIX/lib/python3.10/site-packages/nvidia/cublas/lib:$CONDA_PREFIX/lib/python3.10/site-packages/nvidia/cuda_runtime/lib:${LD_LIBRARY_PATH:-}"
python -m inference.tts.check
```

生成结果在 `runtime/checks/tts.wav`，请实际试听。默认参考音频来自官方示例；项目自己的方言参考录音和准确转写后续再配置。6GB 显存先做短音频、单模型测试。

## 6. 启动应用

```bash
conda activate xiyang-app
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

访问 `http://localhost:8000/` 使用网页，`http://localhost:8000/docs` 查看接口。识别、合成、图片说话需分别启动对应 worker，完整命令见 [运行说明](running.md)。Ctrl+C 停止服务。

提交前检查代码：

```bash
python -m pytest -q
ruff check backend inference tests
```

## 常见问题

| 问题 | 处理 |
|---|---|
| `pkg_resources` 缺失 | 按上述 setuptools 版本和 `--build-constraint` 安装，外层环境降级还不够 |
| DeepSpeed 报 `CUDA_HOME` 缺失 | 基础推理不需要它，使用本仓库 TTS 依赖，不先加装 Toolkit |
| ORT 找不到 CUDA 库或回退 CPU | 核对 ORT 安装源，并执行 TTS 的动态库路径设置 |
| WeText 资源 403 | 当前会回退基础文本处理；数字、日期朗读需要另外检查 |

本机已完成应用测试、模型校验，以及 ASR/TTS 短样本推理和 MuseTalk 两条生成链路。MuseTalk 环境已从零安装；ASR/TTS 沿用原环境，交付前仍需在目标设备完整安装和验收。
