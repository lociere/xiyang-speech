"""Application configuration, independent of machine-specific paths."""
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from inference.config import ROOT


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
    talk_worker_url: str = "http://127.0.0.1:8103"
    model_idle_seconds: float = Field(default=120, ge=0)
    model_start_timeout: float = Field(default=300, gt=0)
    inference_timeout: float = Field(default=300, gt=0)
    talk_inference_timeout: float = Field(default=1800, gt=0)
    max_queued_jobs: int = Field(default=8, ge=1)
    max_audio_seconds: float = Field(default=60, gt=0)
    max_audio_mb: int = Field(default=25, ge=1)
    max_image_mb: int = Field(default=8, ge=1)

    @field_validator("asr_model_dir", "tts_model_dir", "tts_source_dir", "output_dir")
    @classmethod
    def resolve_path(cls, value: Path) -> Path:
        expanded = value.expanduser()
        return (expanded if expanded.is_absolute() else ROOT / expanded).resolve()
