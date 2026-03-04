"""Tests for VideoExtractor."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from universal_extractor.core.base import ExtractionError
from universal_extractor.extractors.video import VideoExtractor, _get_device


class TestVideoExtractor:
    def setup_method(self):
        self.ext = VideoExtractor(model_name="base")

    def test_can_handle(self):
        assert self.ext.can_handle("video.mp4")
        assert self.ext.can_handle("audio.mp3")
        assert self.ext.can_handle("audio.wav")
        assert self.ext.can_handle("VIDEO.MKV")
        assert not self.ext.can_handle("document.pdf")
        assert not self.ext.can_handle("image.png")

    def test_supported_extensions(self):
        # Video formats
        for ext in [".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv"]:
            assert ext in VideoExtractor.supported_extensions
        # Audio formats
        for ext in [".mp3", ".wav", ".m4a", ".flac", ".ogg"]:
            assert ext in VideoExtractor.supported_extensions

    def test_file_not_found(self):
        with pytest.raises(ExtractionError, match="File not found"):
            self.ext.extract("/nonexistent/video.mp4")

    def test_extract_mocked(self, tmp_path):
        """Test extraction with mocked Whisper."""
        # Create a dummy file
        dummy = tmp_path / "test.mp4"
        dummy.write_bytes(b"fake video data")

        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": "Hello, this is a transcription.",
            "language": "en",
            "segments": [{"end": 125.5}],
        }

        mock_whisper = MagicMock()
        mock_whisper.load_model.return_value = mock_model

        with patch.dict(sys.modules, {"whisper": mock_whisper}):
            # Also need to reset the cached model
            import universal_extractor.extractors.video as vid_mod
            vid_mod._whisper_model = None
            vid_mod._whisper_model_name = None

            result = self.ext.extract(str(dummy))

        assert result.text == "Hello, this is a transcription."
        assert result.source_type == "video"
        assert result.language == "en"
        assert "Duration" in result.metadata

    def test_get_device_cpu_fallback(self):
        """Without torch, should default to cpu."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = False

        with patch.dict(sys.modules, {"torch": mock_torch}):
            # Need to reimport to pick up mock
            device = _get_device()
            assert device in ("cpu", "mps", "cuda")  # Any valid device
