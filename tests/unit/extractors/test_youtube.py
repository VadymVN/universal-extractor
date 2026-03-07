"""Tests for YouTubeExtractor."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from universal_extractor.core.base import ExtractionError, ExtractionResult
from universal_extractor.extractors.youtube import CircuitBreaker, YouTubeExtractor


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
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert self.ext._extract_video_id(url) == "dQw4w9WgXcQ"
        assert self.ext._extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
        assert self.ext._extract_video_id("https://youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_extract_video_id_invalid(self):
        with pytest.raises(ExtractionError, match="Cannot extract video ID"):
            self.ext._extract_video_id("https://example.com")

    def test_tier1_success(self):
        """Test tier 1 with mocked youtube-transcript-api v1.x."""
        mock_transcript = MagicMock()
        mock_transcript.fetch.return_value = [{"text": "Hello world"}]

        mock_transcript_list = MagicMock()
        mock_transcript_list.find_manually_created_transcript.return_value = mock_transcript

        mock_api_instance = MagicMock()
        mock_api_instance.list.return_value = mock_transcript_list

        mock_api = MagicMock()
        mock_api.YouTubeTranscriptApi.return_value = mock_api_instance

        with patch.dict(sys.modules, {"youtube_transcript_api": mock_api}):
            result = self.ext._tier1_transcript_api("dQw4w9WgXcQ")

        assert result == "Hello world"

    def test_all_tiers_fail(self):
        """All tiers fail → ExtractionError."""
        # Ensure no real packages are used
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

    def test_is_playlist(self):
        assert YouTubeExtractor.is_playlist(
            "https://www.youtube.com/playlist?list=PLxxxxxxx"
        )
        assert not YouTubeExtractor.is_playlist(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        assert not YouTubeExtractor.is_playlist(
            "https://www.youtube.com/watch?v=abc&list=PLxxx"
        )

    def test_get_playlist_info(self):
        """Test playlist info extraction with mocked yt-dlp."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.__enter__ = MagicMock(return_value=mock_ydl_instance)
        mock_ydl_instance.__exit__ = MagicMock(return_value=False)
        mock_ydl_instance.extract_info.return_value = {
            "title": "My Playlist",
            "entries": [
                {"url": "abc123", "title": "Video A"},
                {"url": "def456", "title": "Video B"},
            ],
        }

        mock_yt_dlp = MagicMock()
        mock_yt_dlp.YoutubeDL.return_value = mock_ydl_instance

        with patch.dict(sys.modules, {"yt_dlp": mock_yt_dlp}):
            ext = YouTubeExtractor(languages=["en"])
            title, videos = ext.get_playlist_info(
                "https://www.youtube.com/playlist?list=PLxxx"
            )

        assert title == "My Playlist"
        assert len(videos) == 2
        assert "abc123" in videos[0][0]
        assert videos[0][1] == "Video A"

    def test_get_playlist_info_empty(self):
        """Empty playlist raises ExtractionError."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.__enter__ = MagicMock(return_value=mock_ydl_instance)
        mock_ydl_instance.__exit__ = MagicMock(return_value=False)
        mock_ydl_instance.extract_info.return_value = {
            "title": "Empty",
            "entries": [],
        }

        mock_yt_dlp = MagicMock()
        mock_yt_dlp.YoutubeDL.return_value = mock_ydl_instance

        with patch.dict(sys.modules, {"yt_dlp": mock_yt_dlp}):
            ext = YouTubeExtractor(languages=["en"])
            with pytest.raises(ExtractionError, match="No accessible videos"):
                ext.get_playlist_info(
                    "https://www.youtube.com/playlist?list=PLxxx"
                )

    def test_extract_playlist(self):
        """Test extract_playlist iterates over videos."""
        ext = YouTubeExtractor(languages=["en"])

        mock_result = ExtractionResult(
            text="transcript",
            source="https://www.youtube.com/watch?v=abc",
            source_type="youtube",
            extractor_name="YouTubeExtractor",
        )

        with patch.object(ext, "get_playlist_info") as mock_info, \
             patch.object(ext, "extract") as mock_extract:
            mock_info.return_value = ("Test Playlist", [
                ("https://www.youtube.com/watch?v=abc", "Vid A"),
                ("https://www.youtube.com/watch?v=def", "Vid B"),
            ])
            mock_extract.return_value = mock_result

            title, results = ext.extract_playlist(
                "https://www.youtube.com/playlist?list=PLxxx"
            )

        assert title == "Test Playlist"
        assert len(results) == 2
        assert mock_extract.call_count == 2

    def test_extract_playlist_partial_failure(self):
        """Playlist extraction continues when individual videos fail."""
        ext = YouTubeExtractor(languages=["en"])

        ok_result = ExtractionResult(
            text="ok", source="url1", source_type="youtube",
            extractor_name="YouTubeExtractor",
        )

        with patch.object(ext, "get_playlist_info") as mock_info, \
             patch.object(ext, "extract") as mock_extract:
            mock_info.return_value = ("PL", [("url1", "T1"), ("url2", "T2")])
            mock_extract.side_effect = [ok_result, Exception("fail")]

            title, results = ext.extract_playlist("https://youtube.com/playlist?list=X")

        assert len(results) == 2
        assert results[0].text == "ok"
        assert results[1].error == "fail"
