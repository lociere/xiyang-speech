# 系统架构

## 服务划分

浏览器仅访问 FastAPI 应用的 8000 端口，静态文件由应用托管。

| 服务 | 环境 | 默认地址 |
|---|---|---|
| 应用与任务调度 | xiyang-app | 127.0.0.1:8000 |
| FunASR | xiyang-asr | 127.0.0.1:8101 |
| CosyVoice3 | xiyang-tts | 127.0.0.1:8102 |
| MuseTalk | MuseTalk | 127.0.0.1:8103 |

各模型使用独立环境和私有 HTTP 接口。Supervisor 管理进程生命周期，应用管理任务执行与模型使用顺序。

## 任务与模型生命周期

三项功能共用一个有界 FIFO 队列，同一时刻执行一个任务、驻留一个模型进程。

1. 应用校验请求并保存上传文件，返回任务编号。
2. 调度器按顺序取出任务，启动所需模型并等待其就绪。
3. 连续使用同一模型时复用进程；切换模型时等待旧进程退出后再加载。
4. 图片加文字任务依次执行 TTS、保存 WAV、停止 TTS、启动 MuseTalk 并生成 MP4。
5. 空闲达到配置时限后停止模型进程；应用继续接收任务。

冷启动发生在首次使用、模型切换和空闲卸载后再次使用时。该调度方式适用于单机串行任务；应用必须保持单进程运行。

## 状态与文件

任务状态保存在输出目录下的 jobs/jobs.sqlite3，上传和生成文件保存在对应任务子目录。完成结果可跨模型切换及应用重启查询；重启时未完成任务标记为失败。

存活、就绪和模型状态分别由 /health、/ready、/api/health 提供，接口定义见 [API](api.md)。备份和清理要求见 [运行说明](running.md)。

## 代码入口

| 文件 | 职责 |
|---|---|
| backend/main.py | 应用生命周期、路由和静态文件托管 |
| backend/manage.py | CLI、启动检查和 Supervisor 配置 |
| backend/runtime.py | 队列、任务持久化及模型调度 |
| backend/routers/jobs.py | 提交、查询和下载接口 |
| backend/routers/health.py | 应用能力和模型状态 |
| inference/config.py | 模型服务共享配置 |
| inference/serve.py | 模型环境动态库设置及服务启动 |
| inference/asr、tts、talk/service.py | 私有模型推理接口 |
| inference/tts/resources.py | WeText 本地资源适配 |
| frontend/js | 表单、任务轮询和结果展示 |
