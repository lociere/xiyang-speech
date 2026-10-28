# 运行与部署

首次安装见 [setup.md](setup.md)。命令在 Linux/WSL 仓库根目录执行。

## 启动与停止

```bash
conda activate xiyang-app
xiyang-speech start
```

访问 http://localhost:8000/。Ctrl+C 停止项目。等价入口为 `python -m backend start`。

在另一个终端激活 xiyang-app 后，可以执行：

```bash
xiyang-speech status
xiyang-speech wait --timeout 60
xiyang-speech stop
```

`status` 显示进程状态，`wait` 等待应用可接收任务，`stop` 等待整体退出。待命模型显示 STOPPED 属于正常状态。

Supervisor 管理应用及模型进程。模型按需加载，切换或空闲超时后退出。调度及任务持久化见 [系统架构](architecture.md)，状态接口见 [HTTP API](api.md)。

## 运行配置

配置模板为 .env.example。相对路径以仓库为基准，环境变量优先于 .env。

| 配置 | 默认值 | 含义 |
|---|---:|---|
| XIYANG_HOST | 127.0.0.1 | 应用监听地址 |
| XIYANG_PORT | 8000 | 应用端口 |
| XIYANG_MODEL_IDLE_SECONDS | 120 | 模型空闲保留秒数，0 表示任务结束后立即退出 |
| XIYANG_MODEL_START_TIMEOUT | 300 | 模型加载超时秒数 |
| XIYANG_INFERENCE_TIMEOUT | 300 | 单阶段推理超时秒数 |
| XIYANG_MAX_QUEUED_JOBS | 8 | 最大等待任务数，不含执行中的一个 |
| XIYANG_MAX_AUDIO_SECONDS | 60 | 上传录音及数字人驱动音频的时长上限 |
| XIYANG_MAX_AUDIO_MB | 25 | 录音体积上限 |
| XIYANG_MAX_IMAGE_MB | 8 | 图片体积上限，另限制 1200 万像素 |

应用必须以单进程运行，不能增加 Uvicorn workers 或启用 reload。模型端口 8101、8102、8103 仅监听回环地址。

可信局域网访问可设置 `XIYANG_HOST=0.0.0.0`，仅开放应用端口。当前应用不提供鉴权；公网部署需配置 HTTPS 和访问控制。

## 日志与数据

- 日志：runtime/processes/app.log、asr.log、tts.log、talk.log。每文件 10 MB，保留 3 份轮转副本。
- 任务及结果：输出目录下的 jobs/jobs.sqlite3 和各任务子目录。
- 应用异常退出后自动重启；模型失败使当前任务失败，后续任务可重新启动模型。
- 加载或推理超时会停止对应模型进程。
- 应用重启后，已完成结果保留，未完成任务标记失败并需重新提交。

```bash
tail -n 80 runtime/processes/tts.log
```

上传和输出保留至人工清理。备份或清理前停止项目，成套处理 jobs 目录，避免单独复制运行中的数据库。

整体停止会终止模型及 FFmpeg 子进程组，各进程最多等待 60 秒后强制结束。

## systemd 部署

模板位于 deploy/systemd/xiyang-speech.service。安装前按实际位置修改 WorkingDirectory 和 ExecStart；模板默认使用 ~/xiyang-speech 和 ~/miniconda3。

先停止前台实例，再安装用户服务：

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/xiyang-speech.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now xiyang-speech
systemctl --user status xiyang-speech
journalctl --user -u xiyang-speech -n 50
```

systemd 运行时使用以下命令管理整套项目：

```bash
systemctl --user stop xiyang-speech
systemctl --user restart xiyang-speech
```

业务就绪以 `xiyang-speech wait` 为准。退出登录后持续运行需由管理员为部署账号启用 linger。WSL 部署必须保持 Windows/WSL 运行。

## 更新与调试

保存本地修改后更新：

```bash
git pull --ff-only
git submodule update --init --recursive
```

依赖或模型清单变化时，按安装文档更新对应环境或资源，验证后重启。

单模块调试前先停止项目，在对应模型环境执行 `python -m inference.serve asr --port 8101`；tts 和 talk 使用各自名称及端口。
