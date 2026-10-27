# 前端

单页 Web 界面，由 FastAPI 托管，原生 ES modules + 手写 CSS，无 Node.js、无构建、无 CDN 依赖。

## 结构

```text
frontend/
  index.html        单页三卡：识别 / 合成 / 图片说话
  css/app.css       样式
  js/
    main.js         标签切换、服务状态栏
    api.js          request / requestBlob / getHealth 等网络封装
    ui.js           toast、按钮加载态、复制
    player.js       音频/视频播放与 Blob 下载
    asr.js          识别：上传音频 → 文字 + 复制
    tts.js          合成：文字 → 音频播放 + 下载
    talk.js         图片说话：图片+文字/音频 → 视频 + 任务进度
```

## 运行

启动应用层后访问 `http://localhost:8000/`：

```bash
conda activate xiyang-app
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

识别、合成需要对应 worker 在 `:8101`、`:8102` 启动。图片说话使用 `:8103` 的真实 MuseTalk worker。浏览器始终只访问应用层 `:8000`，启动方式见 [运行说明](../docs/running.md)。
