# 昔阳方言语音工具

两人开发的本地语音工具，完成以下功能后交付：

- 上传昔阳话音频，识别文字，支持复制。
- 输入文字，生成语音，支持播放和下载。

采用简单 Web 页面、FastAPI、FunASR 和 CosyVoice。应用与两个模型分别使用独立环境，部署在同一台机器。

## 使用文档

- [安装与运行](docs/installation.md)：环境、模型下载、检查和启动，按顺序操作即可。
- [运行说明](docs/running.md)：启动方式、串行内存限制与常见问题。
- [交付说明](docs/delivery.md)：交付内容和功能验收，完成项目时补齐。

## 当前进度

前端页面（识别 / 合成 / 图片说话 mock）与应用层反代接口已完成，ASR 识别与 TTS 合成可用。当前机器内存有限，ASR 与 TTS 两个模型需串行运行，详见[运行说明](docs/running.md)。

待办：worker 的 Web 依赖（fastapi / uvicorn / gdown 等）补进 requirements；真实图片说话（嘴型对齐）模型接入；昔阳方言效果、音质和数字日期朗读待验收。

## 目录

```text
backend/        后端接口和任务处理
frontend/       网页
inference/      模型调用与检查
third_party/    CosyVoice 官方源码子模块
requirements/   各环境依赖文件
config/         模型版本和校验信息
docs/           安装运行、交付说明
tests/          工程测试
training/       后续需要微调时使用
models/         本地模型，不提交 Git
data/           本地录音和数据，不提交 Git
runtime/        生成结果和日志，不提交 Git
```

本地路径在 `.env` 中配置，参考 `.env.example`。提交代码和配置模板即可，模型、录音、密钥及生成结果不提交普通 Git。

两人可按“模型与后端 / 页面与联调”分工；同一仓库协作，交付前在目标电脑完成一次安装和完整使用测试。

## 第三方来源

[FunASR](https://github.com/modelscope/FunASR) 使用固定版本软件包；[CosyVoice](https://github.com/QwenAudio/CosyVoice) 使用固定提交的子模块，保留上游许可证。模型来源和版本见 `config/models.json`，使用及交付条件以对应模型卡为准。
