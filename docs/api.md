# HTTP API

页面提供录音识别与复制、文字合成与音频播放下载、图片+文字/录音生成口型视频与播放下载。使用原生 JS/CSS，浏览器只访问 8000，由应用统一排队并按需启动模型。

## 提交任务

| 路径 | 请求 |
|---|---|
| POST /api/asr/recognize | multipart/form-data，audio 文件 |
| POST /api/tts/synthesize | JSON，text 字符串 |
| POST /api/talk | multipart/form-data，image 文件 + text 或 audio，二选一 |

成功均为 HTTP 202，返回 `{"job_id":"..."}`，不会直接返回文字或 WAV。参数不合法返回 400/422，文件过大 413，等待队列满 429，应用未就绪 503；错误内容为 `detail`。

文本 1–300 字；音频支持 WAV/MP3/M4A/FLAC，默认 25MB/60秒；图片支持 JPG/JPEG/PNG，默认 8MB/1200万像素，需要清晰单人正脸。

## 查询和结果

`GET /api/jobs/{job_id}` 返回：

```json
{
  "job_id": "...",
  "kind": "asr",
  "status": "queued",
  "progress": 0,
  "message": "排队等待中",
  "error": null,
  "result": null,
  "result_url": null,
  "video_url": null
}
```

status 为 queued/running/done/error。progress 是阶段进度，不代表模型内部精确完成比例；优先显示 message。

done 时 result_url 为 `/api/jobs/{job_id}/result`：ASR 返回 JSON `{"text":"..."}`（查询结果中 result 也含该对象），TTS 返回 audio/wav，talk 返回 video/mp4；视频可直接用 URL 播放。兼容路由为 `/api/talk/{id}` 和 `/api/talk/{id}/video`。

前端每 1.5 秒轮询，失败有限重试；加载期间禁用重复提交。图片说话任务在 sessionStorage 保存编号，刷新后继续查询。已完成任务可跨应用重启查询；未完成任务重启后明确失败。当前不提供完整历史列表。

## 状态与生命周期

`/health` 表示应用存活，`/ready` 表示可接收任务。`/api/health` 的 asr/tts/talk 布尔值表示可接收该功能任务，并不表示权重已加载；models 提供 standby/loading/ready/busy/stopping。

待命是正常状态，不能因此禁用功能。加载、切换可能耗时，页面要显示准备中。应用断开才显示暂不可用；后台不探测触发模型加载。任务执行与模型生命周期见 [系统架构](architecture.md)。
