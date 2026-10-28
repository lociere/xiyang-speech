# 前端

原生 JavaScript ES modules 和 CSS，由 FastAPI 托管。

按 [运行说明](../docs/running.md) 启动项目，访问 http://localhost:8000/。前端仅调用应用层 API，三项功能均采用异步任务提交和轮询。

| 文件 | 职责 |
|---|---|
| js/main.js | 标签切换和服务状态 |
| js/api.js | 请求、错误解析和任务轮询 |
| js/asr.js | 录音上传、识别结果和复制 |
| js/tts.js | 文本合成和音频结果 |
| js/talk.js | 人物图片、驱动音频、任务进度和视频结果 |
| js/player.js | 媒体播放和下载 |
| js/ui.js | 提示、按钮状态和复制操作 |

接口定义见 [HTTP API](../docs/api.md)，验收要求见 [交付验收](../docs/delivery.md)。
