"""Tests for YouTubeExtractor."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from universal_extractor.core.base import ExtractionError, ExtractionResult
from universal_extractor.extractors.youtube import (
    CircuitBreaker,
    RateLimitError,
    YouTubeExtractor,
    _is_rate_limit,
)


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


class TestIsRateLimit:
    """Helper detects YouTube IP/rate blocks across naming conventions."""

    def test_detects_named_exceptions(self):
        # Class names mirror upstream youtube-transcript-api (no -Error suffix);
        # _is_rate_limit matches by name, so the test names must match too.
        class IpBlocked(Exception):  # noqa: N818
            pass

        class RequestBlocked(Exception):  # noqa: N818
            pass

        class TooManyRequests(Exception):  # noqa: N818
            pass

        assert _is_rate_limit(IpBlocked("x"))
        assert _is_rate_limit(RequestBlocked("x"))
        assert _is_rate_limit(TooManyRequests("x"))

    def test_detects_http_429_in_message(self):
        assert _is_rate_limit(Exception("HTTP Error 429: Too Many Requests"))
        assert _is_rate_limit(Exception("server returned: too many requests"))

    def test_ignores_unrelated_errors(self):
        assert not _is_rate_limit(ValueError("missing field"))
        assert not _is_rate_limit(Exception("not found"))


class TestRateLimitPropagation:
    """Tier 1 IpBlocked must raise RateLimitError (don't fall through to Tier 2)."""

    def test_tier1_ipblocked_raises_rate_limit_error(self):
        # Mirrors upstream library's exception class name.
        class IpBlocked(Exception):  # noqa: N818
            pass

        # transcript_list.list() raises IpBlocked at the OUTER level
        mock_api_instance = MagicMock()
        mock_api_instance.list.side_effect = IpBlocked("blocked")

        mock_api_module = MagicMock()
        mock_api_module.YouTubeTranscriptApi.return_value = mock_api_instance

        ext = YouTubeExtractor(languages=["en"])
        ext._last_tier_errors = {}  # extract() initializes this; init manually for unit test
        with patch.dict(sys.modules, {"youtube_transcript_api": mock_api_module}):
            with pytest.raises(RateLimitError, match="Tier 1"):
                ext._tier1_transcript_api("dQw4w9WgXcQ")

        assert "IpBlocked" in ext._last_tier_errors[1]

    def test_extract_propagates_rate_limit_skipping_later_tiers(self):
        """When Tier 1 rate-limits, Tier 2 and 3 must NOT be tried."""
        ext = YouTubeExtractor(languages=["en"], enable_whisper=False)
        ext._get_video_title = lambda url: "T"

        with patch.object(ext, "_tier1_transcript_api") as t1, \
             patch.object(ext, "_tier2_ytdlp_subs") as t2, \
             patch.object(ext, "_tier3_whisper") as t3:
            t1.side_effect = RateLimitError("Tier 1 IpBlocked", source="vid")

            with pytest.raises(RateLimitError):
                ext.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

            t1.assert_called_once()
            t2.assert_not_called()
            t3.assert_not_called()


class TestErrorSurfacing:
    """Final ExtractionError includes real per-tier reasons (not just generic)."""

    def test_all_tiers_fail_error_includes_per_tier_reasons(self):
        ext = YouTubeExtractor(languages=["en"], enable_whisper=False)
        ext._get_video_title = lambda url: "T"

        # side_effects on patched methods receive the original args — accept *a.
        def t1(*_a, **_k):
            ext._last_tier_errors[1] = "no usable transcript found"
            return None

        def t2(*_a, **_k):
            ext._last_tier_errors[2] = "NotFoundError: video has no subs"
            return None

        with patch.object(ext, "_tier1_transcript_api", side_effect=t1), \
             patch.object(ext, "_tier2_ytdlp_subs", side_effect=t2), \
             patch.object(ext, "_tier3_whisper", return_value=None):
            with pytest.raises(ExtractionError) as excinfo:
                ext.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        msg = str(excinfo.value)
        assert "T1=" in msg
        assert "no usable transcript" in msg
        assert "T2=" in msg
        assert "NotFoundError" in msg


class TestExtractPlaylistRateLimit:
    """extract_playlist must stop on RateLimitError, returning partial results."""

    def test_breaks_on_rate_limit_with_partial_results(self):
        ext = YouTubeExtractor(languages=["en"])
        ok = ExtractionResult(
            text="ok", source="url1", source_type="youtube",
            extractor_name="YouTubeExtractor",
        )

        with patch.object(ext, "get_playlist_info") as mock_info, \
             patch.object(ext, "extract") as mock_extract, \
             patch("universal_extractor.extractors.youtube.time.sleep"):
            mock_info.return_value = (
                "PL",
                [("url1", "T1"), ("url2", "T2"), ("url3", "T3")],
            )
            mock_extract.side_effect = [
                ok,
                RateLimitError("Tier 1 IpBlocked", source="url2"),
            ]

            title, results = ext.extract_playlist("https://youtube.com/playlist?list=X")

        # url3 must NOT have been attempted — only 2 calls to extract()
        assert mock_extract.call_count == 2
        # Results contain url1 (ok) + url2 (rate-limited error result)
        assert len(results) == 2
        assert results[0].text == "ok"
        assert "RateLimitError" in results[1].error
