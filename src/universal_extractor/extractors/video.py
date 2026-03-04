"""VideoExtractor — local audio/video transcription with Whisper."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import ClassVar

from ..core.base import BaseExtractor, ExtractionError, ExtractionResult

logger = logging.getLogger(__name__)

# Lazy-loaded Whisper model (singleton per process)
_whisper_model = None
_whisper_model_name = None


def _get_device() -> str:
    """Auto-detect best device: MPS (Apple Silicon) -> CUDA -> CPU."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def _load_whisper_model(model_name: str = "base"):
    """Lazy-load Whisper model with device auto-detection."""
    global _whisper_model, _whisper_model_name

    if _whisper_model is not None and _whisper_model_name == model_name:
        return _whisper_model

    import whisper

    device = _get_device()
    logger.info("Loading Whisper model '%s' on %s", model_name, device)

    try:
        _whisper_model = whisper.load_model(model_name, device=device)
    except Exception as e:
        if device != "cpu":
            logger.warning("Failed to load on %s, falling back to CPU: %s", device, e)
            _whisper_model = whisper.load_model(model_name, device="cpu")
        else:
            raise

    _whisper_model_name = model_name
    return _whisper_model


class VideoExtractor(BaseExtractor):
    """Transcribes video/audio files using OpenAI Whisper.

    Supports MPS (Apple Silicon) with automatic CPU fallback on sparse tensor errors.
    """

    supported_extensions: ClassVar[set[str]] = {
        ".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv",  # Video
        ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma",  # Audio
    }
    required_packages: ClassVar[set[str]] = {"whisper", "torch"}

    def __init__(self, model_name: str = "base", language: str | None = None):
        self.model_name = model_name
        self.language = language

    def extract(self, source: str) -> ExtractionResult:
        path = Path(source)
        if not path.exists():
            raise ExtractionError(f"File not found: {source}", source=source)
        if not path.is_file():
            raise ExtractionError(f"Not a file: {source}", source=source)

        try:
            model = _load_whisper_model(self.model_name)
        except Exception as e:
            raise ExtractionError(
                f"Failed to load Whisper model: {e}", source=source, cause=e
            )

        transcribe_opts: dict = {}
        if self.language:
            transcribe_opts["language"] = self.language

        # Transcribe with MPS→CPU fallback
        try:
            result = model.transcribe(str(path), **transcribe_opts)
        except RuntimeError as e:
            if "sparse" in str(e).lower() or "mps" in str(e).lower():
                logger.warning("MPS error, retrying on CPU: %s", e)
                import whisper
                cpu_model = whisper.load_model(self.model_name, device="cpu")
                result = cpu_model.transcribe(str(path), **transcribe_opts)
            else:
                raise ExtractionError(
                    f"Whisper transcription failed: {e}", source=source, cause=e
                )

        text = result.get("text", "").strip()
        detected_lang = result.get("language")

        metadata: dict = {
            "whisper_model": self.model_name,
        }
        if detected_lang:
            metadata["detected_language"] = detected_lang

        # Try to get duration
        segments = result.get("segments", [])
        if segments:
            duration = segments[-1].get("end", 0)
            if duration:
                minutes, seconds = divmod(int(duration), 60)
                hours, minutes = divmod(minutes, 60)
                metadata["Duration"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        return ExtractionResult(
            text=text,
            source=source,
            source_type=(
                "video" if path.suffix in {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv"}
                else "audio"
            ),
            extractor_name=self.__class__.__name__,
            metadata=metadata,
            language=detected_lang,
        )
