"""VideoExtractor — local audio/video transcription with faster-whisper.

Uses faster-whisper (CTranslate2 backend) instead of openai-whisper: no numba
dependency, so it runs on current NumPy (2.4+), is faster, and uses less memory.
Runs on CPU with int8 quantization on Apple Silicon (CTranslate2 has no Metal/MPS
backend); CUDA is used automatically when available.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import ClassVar

from ..core.base import BaseExtractor, ExtractionError, ExtractionResult

logger = logging.getLogger(__name__)

# File extensions handled by this extractor (single source of truth so the
# supported set and the video/audio source_type check never drift apart).
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"}

# Lazy-loaded model (singleton per process, keyed by model name)
_model = None
_model_name = None


def _get_device() -> tuple[str, str]:
    """Auto-detect best device and compute type for CTranslate2.

    Returns (device, compute_type). CTranslate2 supports CPU and CUDA only —
    there is no Metal/MPS backend, so Apple Silicon runs on CPU with int8.
    """
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda", "float16"
    except ImportError:
        pass
    return "cpu", "int8"


def _load_model(model_name: str = "small"):
    """Lazy-load faster-whisper model with device auto-detection."""
    global _model, _model_name

    if _model is not None and _model_name == model_name:
        return _model

    from faster_whisper import WhisperModel

    device, compute_type = _get_device()
    logger.info(
        "Loading faster-whisper model '%s' on %s (%s)",
        model_name, device, compute_type,
    )
    _model = WhisperModel(model_name, device=device, compute_type=compute_type)
    _model_name = model_name
    return _model


class VideoExtractor(BaseExtractor):
    """Transcribes video/audio files using faster-whisper (CTranslate2)."""

    supported_extensions: ClassVar[set[str]] = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS
    required_packages: ClassVar[set[str]] = {"faster_whisper"}

    def __init__(self, model_name: str = "small", language: str | None = None):
        self.model_name = model_name
        self.language = language

    def extract(self, source: str) -> ExtractionResult:
        path = Path(source)
        if not path.exists():
            raise ExtractionError(f"File not found: {source}", source=source)
        if not path.is_file():
            raise ExtractionError(f"Not a file: {source}", source=source)

        try:
            model = _load_model(self.model_name)
        except Exception as e:
            raise ExtractionError(
                f"Failed to load faster-whisper model: {e}", source=source, cause=e
            )

        try:
            segments, info = model.transcribe(
                str(path),
                language=self.language,
                beam_size=5,
            )
            # segments is a lazy generator — iterating runs the transcription
            text = "".join(seg.text for seg in segments).strip()
        except Exception as e:
            raise ExtractionError(
                f"faster-whisper transcription failed: {e}", source=source, cause=e
            )

        detected_lang = getattr(info, "language", None)

        metadata: dict = {
            "whisper_model": self.model_name,
        }
        if detected_lang:
            metadata["detected_language"] = detected_lang

        duration = getattr(info, "duration", None)
        if duration:
            minutes, seconds = divmod(int(duration), 60)
            hours, minutes = divmod(minutes, 60)
            metadata["Duration"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        return ExtractionResult(
            text=text,
            source=source,
            source_type="video" if path.suffix.lower() in VIDEO_EXTENSIONS else "audio",
            extractor_name=self.__class__.__name__,
            metadata=metadata,
            language=detected_lang,
        )
