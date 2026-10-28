"""Load WeText FSTs from the configured local directory.

CosyVoice does not expose WeText's resource path. During model initialization,
temporarily bind its snapshot lookup to the local directory; restore the loader
after the normalizers have opened their FSTs.
"""
from contextlib import contextmanager
from unittest.mock import patch

from inference.config import WETEXT_MODEL_DIR

WETEXT_FILES = tuple(f"{lang}/tn/{kind}.fst"
                     for lang in ("en", "zh") for kind in ("tagger", "verbalizer"))


@contextmanager
def local_wetext_resources(directory=WETEXT_MODEL_DIR):
    for relative in WETEXT_FILES:
        path = directory / relative
        if not path.is_file():
            raise RuntimeError(f"缺少 WeText 资源：{path}；请按 docs/models.md 下载")
        with path.open("rb") as stream:
            if stream.read(43).startswith(b"version https://git-lfs.github.com/spec/v1"):
                raise RuntimeError(f"WeText 文件仍为 Git LFS 指针：{path}，请执行 git lfs pull")

    import wetext.wetext as backend

    def local_snapshot(model_id, *args, **kwargs):
        if model_id != "pengzhendong/wetext":
            raise RuntimeError(f"WeText 请求了未配置的资源：{model_id}")
        return str(directory)

    with patch.object(backend, "snapshot_download", local_snapshot):
        yield
