# 昔阳方言语音工具

三人开发的本地方言展示工具，完成以下功能后交付：

- 上传昔阳话音频，识别文字，支持复制。
- 输入文字，生成语音，支持播放和下载。
- 上传人物图片，配合文字或音频生成说话视频，支持播放和下载。

采用简单 Web 页面、FastAPI、FunASR、CosyVoice 和 MuseTalk。应用与各模型分别使用独立环境，部署在同一台机器。

## 使用文档

- [安装与运行](docs/installation.md)：环境、模型下载、检查和启动，按顺序操作即可。
- [运行说明](docs/running.md)：启动方式、串行内存限制与常见问题。
- [MuseTalk 环境](docs/musetalk.md)：数字人源码、依赖、模型下载和启动。
- [交付说明](docs/delivery.md)：交付内容和功能验收，完成项目时补齐。

## 当前进度

前端页面（识别 / 合成 / 图片说话）与应用层反代接口已实现，ASR 识别与 TTS 合成可用。MuseTalk 已接入真实口型模型；首次配置和验证见 [MuseTalk 环境](docs/musetalk.md)。资源有限时可串行运行，详见[运行说明](docs/running.md)。

待办：昔阳方言效果、音质、数字日期朗读与数字人使用体验待验收。数字人当前自动检测人脸，尚无手动面部/嘴部选择。

## 目录

```text
backend/        后端接口和任务处理
frontend/       网页
inference/      模型调用与检查
third_party/    CosyVoice 和 MuseTalk 官方源码子模块
requirements/   各环境依赖文件
config/         模型版本和校验信息
docs/           安装运行、交付说明
tests/          工程测试
training/       后续需要微调时使用
models/         本地模型，不提交 Git
data/           参考录音、测试样本和本地数据
runtime/        生成结果和日志，不提交 Git
```

应用层配置参考 `.env.example`；模型默认按上面的目录放置，独立 worker 的路径说明见安装文档。模型权重、密钥及生成结果保留本地。仓库已包含测试音频，新增录音是否提交由团队确认。

三人可按“模型与后端 / 页面与联调 / 数字人”分工；同一仓库协作，交付前在目标电脑完成一次安装和完整使用测试。

## 第三方来源

[FunASR](https://github.com/modelscope/FunASR) 使用固定版本软件包；[CosyVoice](https://github.com/QwenAudio/CosyVoice) 和 [MuseTalk](https://github.com/TMElyralab/MuseTalk) 使用固定提交的子模块，保留上游许可证。模型来源和版本见 `config/models.json`，使用及交付条件以对应模型卡为准。
