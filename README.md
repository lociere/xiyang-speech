# 昔阳方言语音工具

提供方言语音识别、语音合成和音频驱动的人物口型视频生成。

- **语音识别**：上传 WAV、MP3、M4A 或 FLAC 录音，显示并复制识别文字。
- **语音合成**：输入文字，使用参考录音生成语音，支持播放和下载。
- **人物口型视频**：上传单人正脸照片，配合文字或录音生成视频，支持播放和下载。

识别采用 FunASR，合成采用 CosyVoice3，人物视频采用 MuseTalk。当前使用预训练模型，方言效果需结合实际样本评估。

## 安装与启动

按 [安装说明](docs/setup.md) 创建环境并安装依赖，按 [资源说明](docs/models.md) 下载模型，配置 .env 和参考录音。

在仓库根目录启动：

```bash
conda activate xiyang-app
xiyang-speech start
```

访问 http://localhost:8000/。按 Ctrl+C 停止项目。

## 文档

- [安装与配置](docs/setup.md)
- [模型与辅助资源](docs/models.md)
- [运行与部署](docs/running.md)
- [系统架构](docs/architecture.md)
- [HTTP API](docs/api.md)
- [依赖管理](requirements/README.md)
- [交付验收](docs/delivery.md)
- [ASR / TTS 小数据训练示例](docs/training.md)

## 目录

| 目录 | 内容 |
|---|---|
| backend | 应用、任务队列和进程管理 |
| frontend | 网页及静态资源 |
| inference | 模型适配、推理服务和资源校验 |
| training | 数据集准备及独立训练参数配置 |
| third_party | 固定提交的 CosyVoice、MuseTalk 子模块 |
| environments | Conda 基础环境定义 |
| requirements | pip 依赖和 GPU wheel 来源 |
| config | 模型及辅助资源清单 |
| deploy | systemd 服务模板 |
| docs / tests | 文档和工程测试 |
| models | 本地模型权重，不纳入版本管理 |
| runtime | 上传、输出、日志及进程状态，不纳入版本管理 |
| data | 参考录音及测试样本 |

本机配置保存在 .env，模板为 .env.example。模型、录音和第三方组件的使用与分发须符合各自授权。

## 第三方组件

[FunASR](https://github.com/modelscope/FunASR)、[CosyVoice](https://github.com/QwenAudio/CosyVoice)、[MuseTalk](https://github.com/TMElyralab/MuseTalk)。第三方许可证保留在对应源码仓库中。
