# MuseTalk 本地环境

在 WSL Ubuntu 中执行，项目根目录为 `~/xiyang-speech`。MuseTalk 使用独立环境，不改 ASR/TTS 环境。

## 1. 源码

```bash
cd ~/xiyang-speech
git submodule update --init --recursive
```

MuseTalk 源码由 `third_party/MuseTalk` 子模块固定；本次配置版本为 `0a89dec45a0192b824e3cf4daf96c239440c5ed8`，推理使用 v1.5 权重。

## 2. Python 与依赖

```bash
conda create -n MuseTalk python=3.10 pip -y --override-channels -c conda-forge
conda activate MuseTalk
python -m pip install pip==25.3 setuptools==80.9.0 wheel
python -m pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118
python -m pip install numpy==1.23.5 scipy==1.15.3
python -m pip install --no-build-isolation chumpy==0.70
python -m pip install -r requirements/talk.txt -f https://download.openmmlab.com/mmcv/dist/cu118/torch2.0.0/index.html
```

`mmcv` 必须安装匹配 CUDA 11.8 / PyTorch 2.0 的预编译 wheel；不要混装 `mmcv-lite`。无需为普通推理安装完整 CUDA 编译工具链，也不需要 TensorFlow 或训练依赖。

## 3. 模型权重

```bash
cd ~/xiyang-speech/third_party/MuseTalk
huggingface-cli download TMElyralab/MuseTalk --revision 2bcb936e2fddb4d86db4c62fd45b387d0c061571 --include 'musetalkV15/*' --local-dir models
huggingface-cli download stabilityai/sd-vae-ft-mse --revision 31f26fdeee1355a5c34592e401dd41e45d25a493 --include config.json diffusion_pytorch_model.bin --local-dir models/sd-vae
huggingface-cli download openai/whisper-tiny --revision 169d4a4341b33bc18d8881c4b69c2e104e1cc0af --include config.json pytorch_model.bin preprocessor_config.json --local-dir models/whisper
huggingface-cli download yzd-v/DWPose --revision 1a7144101628d69ee7a3768d1ee3a094070dc388 --include dw-ll_ucoco_384.pth --local-dir models/dwpose
mkdir -p models/face-parse-bisent
gdown 154JgKpzCPW82qINcVieuPH3fZ2e0P812 -O models/face-parse-bisent/79999_iter.pth
curl -fL https://download.pytorch.org/models/resnet18-5c106cde.pth -o models/face-parse-bisent/resnet18-5c106cde.pth
```

S3FD 人脸检测权重首次导入时会自动下载到 `~/.cache/torch/hub/checkpoints/s3fd-619a316812.pth`。需要离线交付时也要携带该文件。仅推理 v1.5 不需要下载 v1.0 和 SyncNet 训练权重。

模型权重保留本地，不提交 Git。

## 4. 检查与启动

```bash
cd ~/xiyang-speech
conda activate MuseTalk
python -m pip check
python -m inference.verify_models --component talk
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
python -m uvicorn inference.talk.service:app --host 127.0.0.1 --port 8103 --workers 1
```

另开一个终端：

```bash
cd ~/xiyang-speech
conda activate xiyang-app
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

打开 `http://localhost:8000/`，先测试「图片 + 已有 WAV」，成功后再测「图片 + 文字」。文字路径由 Talk worker 调用 `xiyang-tts` Python 子进程，不必另外启动 TTS worker。TTS 环境必须已配置，且 `data/xiyang_prompt.wav` 必须存在。

如果 TTS Python 不在默认的 `~/miniconda3/envs/xiyang-tts/bin/python`，启动 Talk worker 前设置 `XIYANG_TTS_PYTHON` 为实际解释器的绝对路径。

Talk worker 的 `/health` 表示服务在线；完整模型延迟到首个任务加载，因此健康接口成功不等于视频生成已经验证。生成结果位于 `runtime/outputs/talk/`。

上传清晰、面部无遮挡的单人正脸人像；卡通和非人类角色可能无法识别。当前使用自动人脸定位，尚无手动选择面部/嘴部。图片会先做人脸检查，不支持的图片提前返回中文提示；奇数尺寸图片在编码时补齐为偶数尺寸。

任务状态仅存于 worker 内存，重启后旧任务编号不可继续查询；已生成的视频文件仍保留。当前没有自动清理机制，测试产生的文件可在停止服务后从 `runtime/outputs/talk/` 手动清理。

## 5. 本机验证记录（2026-10-27）

- Python 3.10 / PyTorch 2.0.1+cu118，RTX 4050 Laptop；`pip check` 和 MMCV CUDA NMS 算子检查通过。
- `config/models.json` 中 10 个 Talk 权重文件大小和 SHA256 校验通过；源码子模块保持干净。
- 官方示例人像 + 本地 TTS 音频：生成 2.92 秒 H.264/AAC、25fps 视频，并通过 `/api/talk/{job_id}/video` 获取成功。
- 官方示例人像 + 输入文字：TTS 子进程、MuseTalk、应用层视频获取整条链路通过。
- 用户提供的 315×375 人像：生成 316×376、2.92 秒视频；卡通图提前返回人脸检测失败提示。
- 工程测试 10 项通过，Ruff 检查通过。

测试视频留在 `runtime/checks/musetalk-http-test.mp4` 和 `runtime/checks/musetalk-text-test.mp4`，只作本地验证，不属于交付素材。

当前文字路径会先卸载 MuseTalk 主模型、启动 TTS 子进程，再重新加载 MuseTalk，因此每次文字任务都可能需要等待模型切换。后续部署设备资源充足时，可由后端负责人优化模型常驻和音频复用；环境安装本身无需重做。
