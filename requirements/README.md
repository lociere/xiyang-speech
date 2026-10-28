# 依赖管理

安装步骤见 [setup.md](../docs/setup.md)。依赖配置适用于 Linux x86_64 / CPython 3.10.22。

| Conda 环境定义 | 环境名 | GPU wheel 清单 | pip 依赖清单 |
|---|---|---|---|
| [app.yml](../environments/app.yml) | xiyang-app | 无 | app.txt |
| [asr.yml](../environments/asr.yml) | xiyang-asr | asr-cuda.txt | asr.txt |
| [tts.yml](../environments/tts.yml) | xiyang-tts | tts-cuda.txt | tts.txt |
| [talk.yml](../environments/talk.yml) | MuseTalk | talk-cuda.txt | talk.txt |

## 文件职责

- Conda YAML：Python、pip、setuptools、wheel 版本及渠道。
- `*-cuda.txt`：官方 GPU wheel 的 URL 和 SHA256。以对应 pip 清单作为 `-c` 约束安装，再安装完整依赖。
- `app.txt / asr.txt / tts.txt / talk.txt`：固定版本的安装快照。
- `asr.in / tts.in / talk.in`：直接依赖记录；应用直接依赖定义在 pyproject.toml。
- `build-constraints.txt`：ASR/TTS 隔离构建使用的 setuptools/NumPy。
- `talk-build.txt`：chumpy 构建前需要的 NumPy、SciPy、Cython。

模型权重及辅助数据由 [资源清单](../config/models.json) 管理，准备方法见 [models.md](../docs/models.md)。

## 更新要求

修改直接依赖后，在干净环境安装并执行 pip check 和真实短样本推理，再更新版本快照、GPU 来源及安装文档。

版本快照仅适用于上述目标平台，普通包未使用全量哈希锁定。导出清单应移除个人路径和无关包。依赖更新在安装阶段完成，项目启动时不安装或升级依赖。
