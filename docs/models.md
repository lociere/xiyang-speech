# 模型与辅助资源

以下命令在仓库根目录执行。先按 [setup.md](setup.md) 安装环境和依赖。

来源、revision、大小和 SHA256 记录在 `config/models.json`。已有资源可先校验；目录存在时跳过 clone。

## 1. ASR：Fun-ASR-Nano

通过 ModelScope Git LFS 下载指定提交：

```bash
mkdir -p models/asr
GIT_LFS_SKIP_SMUDGE=1 git clone https://www.modelscope.cn/FunAudioLLM/Fun-ASR-Nano-2512.git models/asr/Fun-ASR-Nano-2512
git -C models/asr/Fun-ASR-Nano-2512 checkout --detach 05201c46f1c38592b1567f857c0d56eab3d0d8ef
git -C models/asr/Fun-ASR-Nano-2512 lfs pull
```

## 2. TTS：CosyVoice3

```bash
conda activate xiyang-tts
hf download FunAudioLLM/Fun-CosyVoice3-0.5B-2512 --revision 29e01c4e8d000f4bcd70751be16fa94bf3d85a18 --local-dir models/tts/Fun-CosyVoice3-0.5B-2512 --include 'CosyVoice-BlankEN/*' campplus.onnx configuration.json cosyvoice3.yaml flow.pt hift.pt llm.pt speech_tokenizer_v3.onnx
```

### WeText 中英文文本处理

WeText 负责数字、日期等文本规范化。其 Python 包不包含全部 FST 数据，单独安装 pip 包不够：

```bash
mkdir -p models/tts
GIT_LFS_SKIP_SMUDGE=1 git clone https://www.modelscope.cn/pengzhendong/wetext.git models/tts/wetext
git -C models/tts/wetext checkout --detach 030bb1febce0bd0168549a03e181cd9c1d70c799
git -C models/tts/wetext lfs pull --include=en/tn/tagger.fst,en/tn/verbalizer.fst,zh/tn/tagger.fst,zh/tn/verbalizer.fst
```

TTS 使用中英文 TN 的四个 FST。`XIYANG_WETEXT_MODEL_DIR` 指定本地资源目录，加载适配位于 inference/tts/resources.py。

## 3. MuseTalk 与配套模型

保留上游预期的 models 目录布局。MuseTalk 环境所固定的 Hugging Face Hub 版本提供命令 `huggingface-cli`：

```bash
conda activate MuseTalk
huggingface-cli download TMElyralab/MuseTalk --revision 2bcb936e2fddb4d86db4c62fd45b387d0c061571 --include 'musetalkV15/*' --local-dir third_party/MuseTalk/models
huggingface-cli download stabilityai/sd-vae-ft-mse --revision 31f26fdeee1355a5c34592e401dd41e45d25a493 --include config.json diffusion_pytorch_model.bin --local-dir third_party/MuseTalk/models/sd-vae
huggingface-cli download openai/whisper-tiny --revision 169d4a4341b33bc18d8881c4b69c2e104e1cc0af --include config.json pytorch_model.bin preprocessor_config.json --local-dir third_party/MuseTalk/models/whisper
huggingface-cli download yzd-v/DWPose --revision 1a7144101628d69ee7a3768d1ee3a094070dc388 --include dw-ll_ucoco_384.pth --local-dir third_party/MuseTalk/models/dwpose
mkdir -p third_party/MuseTalk/models/face-parse-bisent
gdown 154JgKpzCPW82qINcVieuPH3fZ2e0P812 -O third_party/MuseTalk/models/face-parse-bisent/79999_iter.pth
curl --fail --location --retry 3 https://download.pytorch.org/models/resnet18-5c106cde.pth -o third_party/MuseTalk/models/face-parse-bisent/resnet18-5c106cde.pth
mkdir -p ~/.cache/torch/hub/checkpoints
curl --fail --location --retry 3 https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth -o ~/.cache/torch/hub/checkpoints/s3fd-619a316812.pth
```

S3FD 是预处理人脸检测器，其权重在 PyTorch 标准缓存目录。若另行设置了 `TORCH_HOME`，应将最后两个命令的缓存位置改为该目录下的 hub/checkpoints；校验器和推理使用相同设置。

## 4. 配置对应关系

| 内容 | 默认位置 | 配置 |
|---|---|---|
| ASR | models/asr/Fun-ASR-Nano-2512 | XIYANG_ASR_MODEL_DIR |
| TTS | models/tts/Fun-CosyVoice3-0.5B-2512 | XIYANG_TTS_MODEL_DIR |
| WeText | models/tts/wetext | XIYANG_WETEXT_MODEL_DIR |
| MuseTalk 配套权重 | third_party/MuseTalk/models | XIYANG_TALK_SOURCE_DIR 对应源码根目录 |
| S3FD | ~/.cache/torch/hub/checkpoints | PyTorch 的 TORCH_HOME |
| 参考录音 | data/xiyang_prompt.wav | XIYANG_REFERENCE_AUDIO |

参考录音由使用者或交付方提供，要求及转换方式见 [安装说明](setup.md)。

## 5. 校验

```bash
conda activate xiyang-app
python -m inference.verify_models
```

校验器按清单核对文件大小及 SHA256。可用 `--component asr`、`--component tts` 或 `--component talk` 单独校验；后两者会同时检查对应辅助资源。

校验命令不修改文件。先完成依赖和资源准备，再运行 `xiyang-speech check` 检查参考录音、环境和端口。

## 转移和离线交付

复制上述资源目录、S3FD 缓存及授权参考录音，再校验同一份清单。目标设备需安装匹配的 Conda/Python 环境。

离线交付需在目标设备断网验证 ASR、TTS 和 MuseTalk 的完整功能。
