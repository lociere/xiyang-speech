"""Application configuration, independent of machine-specific paths."""
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="XIYANG_", env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    asr_model_dir: Path = Path("models/asr/Fun-ASR-Nano-2512")
    tts_model_dir: Path = Path("models/tts/Fun-CosyVoice3-0.5B-2512")
    tts_source_dir: Path = Path("third_party/CosyVoice")
    output_dir: Path = Path("runtime/outputs")
    asr_worker_url: str = "http://127.0.0.1:8101"
    tts_worker_url: str = "http://127.0.0.1:8102"

    @field_validator("asr_model_dir", "tts_model_dir", "tts_source_dir", "output_dir")
    @classmethod
    def resolve_path(cls, value: Path) -> Path:
        expanded = value.expanduser()
        return (expanded if expanded.is_absolute() else ROOT / expanded).resolve()
