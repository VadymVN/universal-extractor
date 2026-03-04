"""Tests for YouTubeExtractor."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from universal_extractor.extractors.youtube import YouTubeExtractor, CircuitBreaker
from universal_extractor.core.base import ExtractionError


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker(threshold=3)
        assert not cb.is_open

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(threshold=2)
        cb.record_failure()
        assert not cb.is_open
        cb.record_failure()
        assert cb.is_open

    def test_resets_on_success(self):
        cb = CircuitBreaker(threshold=2)
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        assert not cb.is_open


class TestYouTubeExtractor:
    def setup_method(self):
        self.ext = YouTubeExtractor(languages=["en"])

    def test_can_handle(self):
        assert self.ext.can_handle("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert self.ext.can_handle("https://youtu.be/dQw4w9WgXcQ")
        assert not self.ext.can_handle("https://example.com")
        assert not self.ext.can_handle("video.mp4")

    def test_extract_video_id(self):
        assert self.ext._extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
        assert self.ext._extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
        assert self.ext._extract_video_id("https://youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_extract_video_id_invalid(self):
        with pytest.raises(ExtractionError, match="Cannot extract video ID"):
            self.ext._extract_video_id("https://example.com")

    def test_tier1_success(self):
        """Test tier 1 with mocked youtube-transcript-api."""
        mock_entry = MagicMock()
        mock_entry.text = "Hello world"

        mock_transcript = MagicMock()
        mock_transcript.fetch.return_value = [mock_entry]

        mock_transcript_list = MagicMock()
        mock_transcript_list.find_manually_created_transcript.return_value = mock_transcript

        mock_api = MagicMock()
        mock_api.YouTubeTranscriptApi.list_transcripts.return_value = mock_transcript_list

        with patch.dict(sys.modules, {"youtube_transcript_api": mock_api}):
            result = self.ext._tier1_transcript_api("dQw4w9WgXcQ")

        assert result == "Hello world"

    def test_all_tiers_fail(self):
        """All tiers fail → ExtractionError."""
        # Ensure no real packages are used
        mock_empty = MagicMock()
        mock_yt_api = MagicMock()
        mock_yt_api.YouTubeTranscriptApi.list_transcripts.side_effect = Exception("no subs")

        mock_yt_dlp = MagicMock()

        with patch.dict(sys.modules, {
            "youtube_transcript_api": mock_yt_api,
            "yt_dlp": mock_yt_dlp,
        }):
            # Disable whisper for this test
            ext = YouTubeExtractor(languages=["en"], enable_whisper=False)
            # Mock _get_video_title to avoid yt_dlp call issues
            ext._get_video_title = lambda url: "Test Video"
            # Mock tier2 to also fail
            ext._tier2_ytdlp_subs = lambda url: None

            with pytest.raises(ExtractionError, match="All extraction tiers failed"):
                ext.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
