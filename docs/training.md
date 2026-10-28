# ASR 与 TTS 小数据训练示例

适用本仓库固定的 FunASR 1.4.15、CosyVoice3 源码及已下载的模型。所有命令从仓库根目录执行。首次依赖和模型安装见 [setup.md](setup.md)、[models.md](models.md)。

## 1. 目的与算力

本示例使用同一人的 12 条录音：10 条训练、1 条验证、1 条测试。它用于了解数据准备、反向传播、保存权重和加载权重的流程。少量样本容易被记住；训练 loss 下降不能证明模型已经学会昔阳话。正式评估需另备足量、内容独立的验证及测试录音。

| 实验 | 训练范围 | 建议设备配置（规划值，非最低保证） |
|---|---|---|
| ASR 示例 | 冻结语音编码器和语言模型，仅更新音频适配器 | 单张 NVIDIA 24 GB GPU，64 GB 内存 |
| TTS 示例 | CosyVoice3 的 LLM 监督微调，保留原 Flow、声码器 | 单张 NVIDIA 48 GB GPU，64–128 GB 内存 |

显存还受音频时长、batch、精度和优化器影响。小数据只减少迭代次数，不会让模型参数及优化器状态按比例变小。正式训练可再按真实数据规模选择多卡、LoRA 或 DeepSpeed；本示例采用单卡训练，不要求部署设备承担训练。

训练前在应用环境执行 `xiyang-speech stop`，避免模型服务与训练争用 GPU。

## 2. 录音及标注

本地数据目录为：

```text
data/training_demo/
  labels.tsv            人工核对的标注及划分
  wav16k/xy001.wav       ASR：16 kHz / 单声道 / PCM 16-bit
  wav24k/xy001.wav       TTS：24 kHz / 单声道 / PCM 16-bit
  asr/train.jsonl        其余为 dev.jsonl、test.jsonl
  tts/train/             其余为 dev/、test/
    wav.scp
    text
    utt2spk
    spk2utt
    instruct
  preparation.json      导出数量及未核对 ID
```

源录音统一存放在 data/wavs，采用 WAV / PCM 16-bit。本地现有源录音保留 48 kHz、双声道，数据准备阶段再生成各模型需要的版本。转换录音的命令本质上是：

```bash
ffmpeg -i "源录音.wav" -ac 1 -ar 16000 -c:a pcm_s16le xy001.wav
```

TTS 使用 `-ar 24000`。转换采样率不能修复噪声、截断或漏字。每条录音应只有一个人、文字完整、无明显背景音乐；本示例限制为 1–30 秒，较长录音按完整语句切分。

### 核对 labels.tsv

用 VS Code 打开 data/training_demo/labels.tsv。这是 UTF-8 的制表符分隔文件：

| 列 | 用途 |
|---|---|
| id | 唯一录音编号，和两种 WAV 文件名对应 |
| source | 相对 labels.tsv 的原始文件路径 |
| text | 录音中实际说出的完整文字 |
| split | train / dev / test / exclude |
| checked | 听过并核对后改为 yes |

当前 text 暂取文件名，不视为已人工确认。核对 xy001–xy011、xy016；不要把方言口语随意改写成书面普通话。xy012、xy013、xy014、xy017、xy020、xy021 的文件名疑似截断，暂时排除；其余未选录音可在补全标注后扩充。

固定划分：xy001–xy010 训练，xy011 验证，xy016 测试。不要把相同录音复制进不同集合。当前同说话人划分只能演示同说话人适配，不能评估对新说话人的泛化能力。

核对后重新导出：

```bash
python -m training.prepare --labels data/training_demo/labels.tsv
```

此命令是数据格式转换工具，不负责安装环境或启动训练。它生成两种音频格式及上游训练器需要的清单；已有 WAV 不重复覆盖，标注清单每次重新生成。修改原音频后，应先移除对应 ID 的派生 WAV 再转换。未核对的选中录音会报错；`--allow-unreviewed` 仅用于预览数据结构。

### 这些清单是什么

ASR JSONL 每行一条记录，包含音频路径、长度和正确文字。user 中的 `!` 是 FunASR 数据读取器的文件路径标记，不是文件名的一部分。speech_length 是约 10 ms 单位的长度元数据，实际声学特征由 WAV 重新提取。

TTS 使用 Kaldi 风格文本清单：

```text
# wav.scp：录音编号 → WAV 的绝对路径（实际文件中不写注释行）
xy001 /absolute/project/data/training_demo/wav24k/xy001.wav

# text：录音编号 → 完整转写
xy001 下午要下雨呢，你早上快点把被子晒了

# utt2spk：录音编号 → 说话人编号
xy001 xiyang_speaker01

# spk2utt：说话人编号 → 该集合中的所有录音编号
xiyang_speaker01 xy001 xy002

# instruct：CosyVoice3 的文本指令前缀
xy001 You are a helpful assistant.<|endofprompt|>
```

wav.scp 本身不是音频，只是普通文本索引。搬到另一台机器后，应重新运行准备命令，更新绝对路径。

## 3. ASR 训练

### 环境及命令

使用与推理环境隔离的训练环境，避免调参时影响应用依赖。首次可直接克隆已经按安装文档配置的 ASR 环境，无需另装 DeepSpeed：

```bash
conda create -n xiyang-asr-train --clone xiyang-asr
conda activate xiyang-asr-train
python -m pip check
python -m funasr.bin.train_ds \
  --config-path "$PWD/training/configs" \
  --config-name asr_tiny
```

训练器读取本地预训练模型，再合并 training/configs/asr_tiny.yaml。第一轮仅训练 1 epoch，batch 为 1。正常结束应有验证 loss 日志及 runtime/training/asr-tiny 下的 model.pt、model.pt.best 或分轮次权重。输出可能同时包含优化器状态，需预留数 GB 磁盘空间。重复独立实验请更换 output_dir，续训再设置 resume，避免混用实验结果。

### 在哪里调参数

直接编辑 training/configs/asr_tiny.yaml：

| 配置项 | 当前值 | 含义 |
|---|---:|---|
| train_conf.max_epoch | 1 | 完整遍历训练集次数 |
| optim_conf.lr | 0.00001 | 学习率 |
| dataset_conf.batch_size | 1 | 每批录音条数 |
| train_conf.accum_grad | 1 | 梯度累计批数 |
| train_conf.grad_clip | 5 | 梯度裁剪阈值 |
| scheduler_conf.warmup_steps | 2 | 学习率预热步数 |
| train_conf.validate_interval | 10 | 按步验证间隔 |
| train_conf.save_checkpoint_interval | 10 | 按步存档间隔 |
| audio_adaptor_conf.freeze | false | 允许更新音频适配器 |
| audio_encoder_conf.freeze / llm_conf.freeze | true | 冻结编码器及语言模型 |

ASR 不是通过设置“昔阳县”开关学习方言，而是通过音频与正确转写的监督配对更新可训练参数。先保持冻结范围，确认小流程后再扩大数据和实验范围。

### 加载微调结果

先停止应用，切回推理环境，对保留的测试录音分别跑基线及微调模型：

```bash
conda activate xiyang-asr
python -m inference.asr.check \
  --audio data/training_demo/wav16k/xy016.wav \
  --output runtime/training/asr-baseline-test.json
python -m inference.asr.check \
  --audio data/training_demo/wav16k/xy016.wav \
  --checkpoint runtime/training/asr-tiny/model.pt.best \
  --output runtime/training/asr-finetuned-test.json
```

如训练器实际输出的文件名不同，将 --checkpoint 指向实际 checkpoint。保持基础模型目录不变，单独覆盖 checkpoint；不要把含优化器状态的文件当作模型目录。

逐字对照测试转写，正式测试集统计 CER（替换、删除、插入字数之和 / 正确字数），并统一标点、空格等计算规则。只有一条测试录音的结果不足以证明质量提升。

## 4. TTS 训练

本仓库固定的 CosyVoice3 [官方训练配方](https://github.com/QwenAudio/CosyVoice/blob/074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc/examples/libritts/cosyvoice3/run.sh)目前说明优先支持 LLM 训练。这里仅微调 LLM，不盲目同时训练 Flow、HiFT。

### 训练环境

```bash
conda create -n xiyang-tts-train --clone xiyang-tts
conda activate xiyang-tts-train
conda install -n xiyang-tts-train --file environments/tts-cuda-dev-linux-64.explicit.txt
export CUDA_HOME="$CONDA_PREFIX"
export PATH="$CUDA_HOME/bin:$PATH"
nvcc --version
DS_BUILD_OPS=0 python -m pip install --no-build-isolation -r requirements/tts-train.txt
python -m pip check
```

CUDA 开发组件固定为 12.1 系列，与该环境 PyTorch cu121 匹配。安装采用 [Conda 标准 explicit 清单](https://conda.org/learn/specifications/exchange/text-spec/)，固定 6 个 CUDA 包的版本、官方 Anaconda API 下载地址及 MD5 校验值，不重新求解软件源索引。清单仅用于已配置的 xiyang-tts 克隆环境，适用 Linux x86_64 / WSL2；它不是完整 Python 环境定义，不能单独用它创建训练环境。

安装完成后，验收 CUDA 和训练依赖：

```bash
python -c "import torch, deepspeed; from torch.utils.cpp_extension import CUDA_HOME; print('torch:', torch.__version__); print('CUDA_HOME:', CUDA_HOME); print('deepspeed:', deepspeed.__version__); print('CUDA available:', torch.cuda.is_available()); print('CUDA calculation:', torch.tensor([1., 2.], device='cuda').square().sum().item())"
```

应看到 torch 为 2.3.1+cu121、DeepSpeed 为 0.15.1、CUDA_HOME 指向当前训练环境、CUDA available 为 True、CUDA calculation 为 5.0；前面的 nvcc 应显示 release 12.1，pip check 应无依赖冲突。这些检查确认训练环境基本可用，不代表已完成模型训练或证明显存足够。

DeepSpeed 0.15.1 是上游该提交的依赖，即使选择 torch_ddp，训练入口也会导入它；`DS_BUILD_OPS=0` 不提前编译可选算子。本流程不启用 DeepSpeed 训练引擎。这里仅安装 nvcc、CUDA 运行时开发头文件和静态链接文件、驱动链接桩及 CCCL，不安装 Nsight 或整套静态计算库。PyTorch 的 GPU 运行库仍由原有 wheel 提供；这些开发组件只装在训练环境，不更改系统驱动。

重新打开训练终端后，激活训练环境并重新设置 CUDA_HOME。若安装器或 import 报错，应解决该训练环境的问题，不要升级现有推理环境来尝试修复。

若下载出现 HTTP 522、连接超时或断开，先等待安装命令退出，再重试同一条清单安装命令；Conda 会复用有效缓存。只有清单中的包全部已缓存时，才可增加 `--offline` 完成本地安装。出现下载错误不代表安装成功，不能跳过安装直接执行 nvcc 或训练。若提示 nvcc 找不到，先确认安装成功，再核对 CUDA_HOME 和 PATH；不要同时执行系统 apt 安装来修补这个 Conda 环境。

### 路径与额外训练资源

```bash
export XIYANG_TRAIN_ROOT="$PWD"
export PYTHONPATH="$XIYANG_TRAIN_ROOT/third_party/CosyVoice:$XIYANG_TRAIN_ROOT/third_party/CosyVoice/third_party/Matcha-TTS${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="$(python -c 'import sys; from pathlib import Path; from inference.serve import library_paths; print(":".join(library_paths(Path(sys.prefix))))')${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
huggingface-cli download FunAudioLLM/Fun-CosyVoice3-0.5B-2512 \
  speech_tokenizer_v3.batch.onnx --revision 29e01c4 \
  --local-dir "$XIYANG_TRAIN_ROOT/models/training/cosyvoice3-onnx"
cp models/tts/Fun-CosyVoice3-0.5B-2512/campplus.onnx \
  models/training/cosyvoice3-onnx/campplus.onnx
```

batch tokenizer 是约 969 MB 的训练资源，和推理使用的 speech_tokenizer_v3.onnx 不同。上游训练入口即使使用预提取 token，也会初始化这个 batch 模型。它在[官方权重仓库](https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512/tree/29e01c4)提供；下载放入独立训练资源目录，不覆盖已校验的推理模型。

动态库路径由当前环境的 PyTorch / NVIDIA wheel 目录生成，和模型服务启动时使用同一规则，使 ONNX Runtime 能找到对应的 CUDA / cuDNN 库。每次切换环境后应在新终端重新设置，不把旧环境的路径长期写入系统配置。

### 特征与 Parquet 数据

下面的循环只是依次对 train、dev、test 调用上游数据工具；参数路径均为准备命令生成的实际文件：

```bash
for split in train dev test; do
  python third_party/CosyVoice/tools/extract_embedding.py \
    --dir "$XIYANG_TRAIN_ROOT/data/training_demo/tts/$split" \
    --onnx_path "$XIYANG_TRAIN_ROOT/models/tts/Fun-CosyVoice3-0.5B-2512/campplus.onnx" \
    --num_thread 1
  python third_party/CosyVoice/tools/extract_speech_token.py \
    --dir "$XIYANG_TRAIN_ROOT/data/training_demo/tts/$split" \
    --onnx_path "$XIYANG_TRAIN_ROOT/models/tts/Fun-CosyVoice3-0.5B-2512/speech_tokenizer_v3.onnx" \
    --num_thread 1
  mkdir -p "data/training_demo/tts/$split/parquet"
  python third_party/CosyVoice/tools/make_parquet_list.py \
    --num_utts_per_parquet 100 --num_processes 1 \
    --src_dir "$XIYANG_TRAIN_ROOT/data/training_demo/tts/$split" \
    --des_dir "$XIYANG_TRAIN_ROOT/data/training_demo/tts/$split/parquet"
done
```

应得到 utt2embedding.pt、spk2embedding.pt、utt2speech_token.pt、parquet/data.list 和 parquet_000000000.tar。这个 .tar 实际由上游按 Parquet 格式写入，不要当 tar 压缩包解压。检查日志中没有被跳过的录音或空 speech token；更改标注或划分后需要重新生成特征/Parquet，不能只修改 TSV 就直接训练。

### 启动 LLM 微调

```bash
torchrun --standalone --nnodes=1 --nproc_per_node=1 \
  third_party/CosyVoice/cosyvoice/bin/train.py \
  --train_engine torch_ddp --model llm \
  --config "$XIYANG_TRAIN_ROOT/training/configs/tts_tiny.yaml" \
  --train_data "$XIYANG_TRAIN_ROOT/data/training_demo/tts/train/parquet/data.list" \
  --cv_data "$XIYANG_TRAIN_ROOT/data/training_demo/tts/dev/parquet/data.list" \
  --qwen_pretrain_path "$XIYANG_TRAIN_ROOT/models/tts/Fun-CosyVoice3-0.5B-2512/CosyVoice-BlankEN" \
  --onnx_path "$XIYANG_TRAIN_ROOT/models/training/cosyvoice3-onnx" \
  --checkpoint "$XIYANG_TRAIN_ROOT/models/tts/Fun-CosyVoice3-0.5B-2512/llm.pt" \
  --model_dir "$XIYANG_TRAIN_ROOT/runtime/training/tts-tiny" \
  --tensorboard_dir "$XIYANG_TRAIN_ROOT/runtime/training/tensorboard" \
  --num_workers 1 --prefetch 2 --pin_memory --use_amp
```

首次运行不使用 `xiyang-speech start`，它是推理应用入口。训练器由 torchrun 单独启动。结束应有验证 loss、epoch_0_whole.pt 及对应 YAML；checkpoint 含训练元数据，需要用官方 average_model 导出干净权重。

参数位于 training/configs/tts_tiny.yaml：

| 配置项 | 当前值 | 含义 |
|---|---:|---|
| train_conf.max_epoch | 1 | 先跑一轮验证流程 |
| train_conf.optim_conf.lr | 0.00001 | LLM 微调学习率 |
| train_conf.accum_grad | 1 | 梯度累计批数 |
| batch.max_frames_in_batch | 600 | 动态 batch 的声学帧预算，不是固定录音条数 |
| padding.use_spk_embedding | true | 单说话人 SFT 使用说话人平均 embedding |
| train_conf.log_interval | 1 | 每步记录日志 |

sample_rate、词表大小和网络结构必须与预训练权重匹配，不要作为常规调参项目修改。配置从固定版本官方配方派生，保留了其网络、数据管线及 Apache-2.0 授权来源。

### 导出及试听

先创建独立目录，保留原模型不变：

```bash
mkdir -p models/tts/xiyang-tiny
cp --reflink=auto models/tts/Fun-CosyVoice3-0.5B-2512/{cosyvoice3.yaml,campplus.onnx,speech_tokenizer_v3.onnx,flow.pt,hift.pt} models/tts/xiyang-tiny/
cp -r --reflink=auto models/tts/Fun-CosyVoice3-0.5B-2512/CosyVoice-BlankEN models/tts/xiyang-tiny/
python third_party/CosyVoice/cosyvoice/bin/average_model.py \
  --src_path runtime/training/tts-tiny \
  --dst_model models/tts/xiyang-tiny/llm.pt --num 1 --val_best
```

`--num 1` 仅导出验证集最优的单个 checkpoint；正式多轮实验可改成多个优选权重平均。检查输出实际选择的 epoch，不能误导出 init.pt。

切回 TTS 推理环境，以训练集中的短录音作参考、以新句子作目标文本：

```bash
conda activate xiyang-tts
export LD_LIBRARY_PATH="$(python -c 'import sys; from pathlib import Path; from inference.serve import library_paths; print(":".join(library_paths(Path(sys.prefix))))')${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
python -m inference.tts.check \
  --model-dir models/tts/xiyang-tiny \
  --prompt-audio data/training_demo/wav24k/xy001.wav \
  --prompt-text 'You are a helpful assistant.<|endofprompt|>下午要下雨呢，你早上快点把被子晒了' \
  --text '明天早上你去他家坐一坐，中午就能走了。' \
  --output runtime/training/tts-finetuned-test.wav
```

参考文字必须与核对后的 xy001 录音一致。再用相同参考音频、相同目标句对基础模型运行一次，输出另一文件，比较清晰度、漏读重复、音色和方言发音。验证及测试录音不作训练数据；这里的目标句来自保留测试条目，正式评测还需增加未见过的新句子。

训练结果先离线验收，不自动替换应用 .env 或基础权重。满意后再建立正式模型版本、记录数据和配置快照，并在部署前验证接口及视频链路。

## 5. 首轮完成标准

1. 人工确认选中的逐字转写，数据长度、采样率和集合划分正确。
2. 训练中有有限的 loss，权重可保存、重新加载，没有只加载基础模型而误以为使用了微调结果。
3. 固定测试集对比基线；保留失败样本，不用训练集表现代替质量评价。
4. 当前 tiny 配置只做流程演示；扩充已核对的数据、独立验证集后，再决定正式训练轮数及学习率。

data 下的录音、标注及训练数据清单纳入 Git。models 和 runtime 仍不纳入 Git，预训练及微调权重按资源说明或交付约定单独分发。数据清单中的绝对路径在另一台机器上使用前，应按本文重新导出。
