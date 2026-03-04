"""Configuration dataclass with env var support."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    """Configuration for universal_extractor.

    Priority: constructor args > env vars > defaults.
    Env vars use the UNIEXTRACT_ prefix.
    """

    whisper_model: str = "base"
    whisper_language: str | None = None
    enable_whisper: bool = True
    youtube_languages: list[str] = field(default_factory=lambda: ["en", "ru"])
    web_timeout: int = 30
    max_workers: int = 4
    log_level: str = "INFO"
    output_dir: str = "output"

    @classmethod
    def from_env(cls, **overrides: object) -> Config:
        """Create config from environment variables, with optional overrides."""
        env_map: dict[str, tuple[str, type]] = {
            "whisper_model": ("UNIEXTRACT_WHISPER_MODEL", str),
            "whisper_language": ("UNIEXTRACT_WHISPER_LANGUAGE", str),
            "enable_whisper": ("UNIEXTRACT_ENABLE_WHISPER", bool),
            "web_timeout": ("UNIEXTRACT_WEB_TIMEOUT", int),
            "max_workers": ("UNIEXTRACT_MAX_WORKERS", int),
            "log_level": ("UNIEXTRACT_LOG_LEVEL", str),
            "output_dir": ("UNIEXTRACT_OUTPUT_DIR", str),
        }

        kwargs: dict[str, object] = {}
        for field_name, (env_var, field_type) in env_map.items():
            val = os.environ.get(env_var)
            if val is not None:
                if field_type is bool:
                    kwargs[field_name] = val.lower() in ("1", "true", "yes")
                elif field_type is int:
                    kwargs[field_name] = int(val)
                else:
                    kwargs[field_name] = val

        # YouTube languages from comma-separated env var
        yt_langs = os.environ.get("UNIEXTRACT_YOUTUBE_LANGUAGES")
        if yt_langs:
            kwargs["youtube_languages"] = [l.strip() for l in yt_langs.split(",")]

        kwargs.update(overrides)
        return cls(**kwargs)  # type: ignore[arg-type]

    def validate(self) -> list[str]:
        """Validate config values. Returns list of error messages (empty if valid)."""
        errors = []
        valid_models = {"tiny", "base", "small", "medium", "large"}
        if self.whisper_model not in valid_models:
            errors.append(
                f"Invalid whisper_model '{self.whisper_model}'. "
                f"Must be one of: {', '.join(sorted(valid_models))}"
            )
        if self.web_timeout < 1:
            errors.append(f"web_timeout must be >= 1, got {self.web_timeout}")
        if self.max_workers < 1:
            errors.append(f"max_workers must be >= 1, got {self.max_workers}")
        return errors
