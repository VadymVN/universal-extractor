"""YouTubeExtractor — 3-tier fallback with circuit breaker."""

from __future__ import annotations

import logging
import re
import tempfile
import time
from typing import ClassVar

from ..core.base import BaseExtractor, ExtractionError, ExtractionResult

logger = logging.getLogger(__name__)

# Silence yt-dlp's own ERROR/WARNING output (we handle errors ourselves)
_ytdlp_logger = logging.getLogger("yt_dlp.quiet")
_ytdlp_logger.setLevel(logging.CRITICAL)

# Delay between consecutive YouTube requests to avoid 429 rate limiting
_PLAYLIST_DELAY_SECONDS = 6.0

# Retry settings for Tier 1 transcript fetch under rate limiting
_TIER1_FETCH_RETRIES = 3
_TIER1_FETCH_BACKOFF = 5.0


class CircuitBreaker:
    """Simple circuit breaker: after N consecutive failures, skip the method."""

    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self.failures = 0

    def record_failure(self) -> None:
        self.failures += 1

    def record_success(self) -> None:
        self.failures = 0

    @property
    def is_open(self) -> bool:
        return self.failures >= self.threshold


class YouTubeExtractor(BaseExtractor):
    """Extracts transcripts from YouTube videos using a 3-tier fallback.

    Tier 1: youtube-transcript-api (fast, ~0.5s)
    Tier 2: yt-dlp subtitle download (~1-2s)
    Tier 3: Whisper local transcription (~30-120s)
    """

    supported_extensions: ClassVar[set[str]] = set()
    supported_url_patterns: ClassVar[set[str]] = {"youtube.com", "youtu.be"}
    required_packages: ClassVar[set[str]] = set()  # All optional, checked at runtime

    _yt_dlp_breaker = CircuitBreaker(threshold=3)

    def __init__(
        self,
        languages: list[str] | None = None,
        enable_whisper: bool = True,
        whisper_model: str = "base",
        cookies_from_browser: str | None = None,
    ):
        self.languages = languages or ["en", "ru"]
        self.enable_whisper = enable_whisper
        self.whisper_model = whisper_model
        self.cookies_from_browser = cookies_from_browser
        self._whisper_model_cache = None
        self._has_impersonation = self._check_impersonation()

    @staticmethod
    def _check_impersonation() -> bool:
        """Check if curl-cffi and yt-dlp impersonation are available."""
        try:
            import curl_cffi  # noqa: F401
            from yt_dlp.networking.impersonate import ImpersonateTarget  # noqa: F401
            return True
        except ImportError:
            return False

    def _ytdlp_base_opts(self) -> dict:
        """Base yt-dlp options with rate limiting and optional impersonation."""
        opts: dict = {
            "quiet": True,
            "no_warnings": True,
            "logger": _ytdlp_logger,
            "sleep_requests": 1,
            "sleep_interval": 3,
            "max_sleep_interval": 5,
            "sleep_subtitles": 3,
        }
        if self.cookies_from_browser:
            opts["cookiesfrombrowser"] = (self.cookies_from_browser,)
        if self._has_impersonation:
            from yt_dlp.networking.impersonate import ImpersonateTarget
            opts["impersonate"] = ImpersonateTarget.from_str("chrome")
            logger.debug("yt-dlp impersonation enabled (curl-cffi available)")
        return opts

    @staticmethod
    def is_playlist(url: str) -> bool:
        """Check if a YouTube URL points to a playlist."""
        return "list=" in url and "/watch?" not in url or "/playlist?" in url

    def get_playlist_info(self, url: str) -> tuple[str, list[tuple[str, str]]]:
        """Get playlist title and list of (video_url, video_title) via yt-dlp.

        Returns (playlist_title, [(video_url, video_title), ...]).
        """
        try:
            import yt_dlp
        except ImportError as exc:
            raise ExtractionError(
                "yt-dlp is required for playlist extraction", source=url
            ) from exc

        opts = self._ytdlp_base_opts()
        opts["extract_flat"] = True
        opts["skip_download"] = True
        opts["ignoreerrors"] = True

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            raise ExtractionError(
                f"Failed to fetch playlist info (playlist may be private or deleted): {e}",
                source=url,
            ) from e

        if info is None:
            raise ExtractionError(
                f"Playlist is private, deleted, or unavailable: {url}",
                source=url,
            )

        title = info.get("title", "playlist")
        entries = info.get("entries", [])
        videos: list[tuple[str, str]] = []
        for entry in entries:
            if entry is None:
                continue
            vid_url = entry.get("url") or entry.get("webpage_url")
            if vid_url:
                if not vid_url.startswith("http"):
                    vid_url = f"https://www.youtube.com/watch?v={vid_url}"
                vid_title = entry.get("title", "")
                videos.append((vid_url, vid_title))

        if not videos:
            raise ExtractionError(
                f"No accessible videos found in playlist: {url}",
                source=url,
            )

        return title, videos

    def extract_playlist(
        self,
        url: str,
        skip_urls: set[str] | None = None,
    ) -> tuple[str, list[ExtractionResult]]:
        """Extract transcripts from all videos in a playlist.

        Args:
            url: YouTube playlist URL.
            skip_urls: Set of video URLs to skip (e.g. already processed).

        Returns (playlist_title, [ExtractionResult, ...]).
        Failed videos are included with error field set.
        Skipped videos are NOT included in results.
        """
        title, videos = self.get_playlist_info(url)
        results: list[ExtractionResult] = []
        _skip = skip_urls or set()

        for i, (video_url, video_title) in enumerate(videos):
            if video_url in _skip:
                logger.debug("Skipping already-known video: %s", video_url)
                continue
            if results:
                time.sleep(_PLAYLIST_DELAY_SECONDS)
            try:
                result = self.extract(video_url, title_hint=video_title)
                results.append(result)
            except Exception as e:
                logger.error("Failed to extract %s: %s", video_url, e)
                results.append(
                    ExtractionResult(
                        text="",
                        source=video_url,
                        source_type="youtube",
                        extractor_name=self.__class__.__name__,
                        metadata={"Title": video_title} if video_title else {},
                        error=str(e),
                    )
                )

        return title, results

    def _extract_video_id(self, url: str) -> str:
        """Extract YouTube video ID from URL."""
        patterns = [
            r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
            r"(?:embed/)([a-zA-Z0-9_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        raise ExtractionError(f"Cannot extract video ID from: {url}", source=url)

    def _get_video_title(self, url: str) -> str:
        """Try to get video title via yt-dlp."""
        try:
            import yt_dlp

            opts = self._ytdlp_base_opts()
            opts["skip_download"] = True
            opts["extract_flat"] = True
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info.get("title", "")
        except Exception:
            return ""

    @staticmethod
    def _fetch_with_retry(transcript) -> list:
        """Fetch transcript with exponential backoff on rate limiting."""
        last_exc = None
        for attempt in range(_TIER1_FETCH_RETRIES + 1):
            try:
                return transcript.fetch()
            except Exception as e:
                last_exc = e
                if attempt < _TIER1_FETCH_RETRIES:
                    wait = _TIER1_FETCH_BACKOFF * (2 ** attempt)
                    logger.debug("Tier 1 fetch blocked, retrying in %.1fs...", wait)
                    time.sleep(wait)
        raise last_exc  # type: ignore[misc]

    def _tier1_transcript_api(self, video_id: str) -> str | None:
        """Tier 1: youtube-transcript-api (v1.x API)."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError:
            logger.debug("youtube-transcript-api not installed, skipping tier 1")
            return None

        try:
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.list(video_id)

            # Try manual transcripts first
            for lang in self.languages:
                try:
                    transcript = transcript_list.find_manually_created_transcript([lang])
                    entries = self._fetch_with_retry(transcript)
                    text = " ".join(
                        e.get("text", "") if isinstance(e, dict) else e.text
                        for e in entries
                    )
                    logger.info("Tier 1 (manual subs, %s): success", lang)
                    return text
                except Exception:
                    continue

            # Try auto-generated
            for lang in self.languages:
                try:
                    transcript = transcript_list.find_generated_transcript([lang])
                    entries = self._fetch_with_retry(transcript)
                    text = " ".join(
                        e.get("text", "") if isinstance(e, dict) else e.text
                        for e in entries
                    )
                    logger.info("Tier 1 (auto subs, %s): success", lang)
                    return text
                except Exception:
                    continue

            # Try any available transcript
            try:
                for transcript in transcript_list:
                    entries = self._fetch_with_retry(transcript)
                    text = " ".join(
                        e.get("text", "") if isinstance(e, dict) else e.text
                        for e in entries
                    )
                    logger.info("Tier 1 (any language): success")
                    return text
            except Exception:
                pass

        except Exception as e:
            logger.debug("Tier 1 failed: %s", e)

        return None

    def _tier2_ytdlp_subs(self, url: str) -> str | None:
        """Tier 2: yt-dlp subtitle download."""
        if self._yt_dlp_breaker.is_open:
            logger.debug("yt-dlp circuit breaker is open, skipping tier 2")
            return None

        try:
            import yt_dlp
        except ImportError:
            logger.debug("yt-dlp not installed, skipping tier 2")
            return None

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                opts = self._ytdlp_base_opts()
                opts.update({
                    "writesubtitles": True,
                    "writeautomaticsub": True,
                    "subtitleslangs": self.languages,
                    "subtitlesformat": "json3/vtt/srt",
                    "skip_download": True,
                    "ignore_no_formats_error": True,
                    "outtmpl": f"{tmp_dir}/%(id)s.%(ext)s",
                })

                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])

                # Find subtitle files
                import glob
                import json
                from pathlib import Path

                sub_files = glob.glob(f"{tmp_dir}/*.json3") + glob.glob(f"{tmp_dir}/*.vtt")

                for sub_file in sub_files:
                    content = Path(sub_file).read_text(encoding="utf-8")
                    if sub_file.endswith(".json3"):
                        data = json.loads(content)
                        events = data.get("events", [])
                        texts = []
                        for event in events:
                            segs = event.get("segs", [])
                            for seg in segs:
                                t = seg.get("utf8", "").strip()
                                if t and t != "\n":
                                    texts.append(t)
                        if texts:
                            self._yt_dlp_breaker.record_success()
                            logger.info("Tier 2 (yt-dlp json3): success")
                            return " ".join(texts)
                    else:
                        # VTT/SRT: strip timestamps and metadata
                        lines = []
                        for line in content.splitlines():
                            line = line.strip()
                            if not line or "-->" in line or line.isdigit():
                                continue
                            if line.startswith("WEBVTT") or line.startswith("Kind:"):
                                continue
                            # Remove VTT tags
                            clean = re.sub(r"<[^>]+>", "", line)
                            if clean.strip():
                                lines.append(clean.strip())
                        if lines:
                            self._yt_dlp_breaker.record_success()
                            logger.info("Tier 2 (yt-dlp vtt/srt): success")
                            return " ".join(lines)

        except Exception as e:
            self._yt_dlp_breaker.record_failure()
            logger.debug("Tier 2 failed: %s", e)

        return None

    def _load_whisper_model(self):
        """Load and cache the Whisper model with MPS/CUDA/CPU auto-detection."""
        if self._whisper_model_cache is not None:
            return self._whisper_model_cache

        import whisper

        device = "cpu"
        try:
            import torch

            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
        except ImportError:
            pass

        logger.info(
            "Loading Whisper model '%s' on %s...", self.whisper_model, device
        )

        try:
            model = whisper.load_model(self.whisper_model, device=device)
        except Exception:
            if device != "cpu":
                logger.warning(
                    "Failed to load on %s, falling back to CPU", device
                )
                model = whisper.load_model(self.whisper_model, device="cpu")
            else:
                raise

        self._whisper_model_cache = model
        return model

    def _tier3_whisper(self, url: str) -> str | None:
        """Tier 3: Download audio and transcribe with Whisper."""
        if not self.enable_whisper:
            logger.debug("Whisper disabled, skipping tier 3")
            return None

        try:
            import whisper  # noqa: F401
            import yt_dlp
        except ImportError:
            logger.debug("whisper/yt-dlp not installed, skipping tier 3")
            return None

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                audio_path = f"{tmp_dir}/audio.mp3"
                opts = self._ytdlp_base_opts()
                opts.update({
                    "format": "bestaudio/best",
                    "outtmpl": audio_path,
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                    }],
                })

                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])

                # Find the audio file (yt-dlp may add extension)
                import glob

                audio_files = glob.glob(f"{tmp_dir}/audio*")
                if not audio_files:
                    return None

                logger.info("Tier 3: transcribing with Whisper...")
                model = self._load_whisper_model()
                result = model.transcribe(audio_files[0])
                text = result.get("text", "")

                if text:
                    logger.info("Tier 3 (Whisper): success")
                    return text

        except Exception as e:
            logger.debug("Tier 3 failed: %s", e)

        return None

    def extract(self, source: str, title_hint: str = "") -> ExtractionResult:
        video_id = self._extract_video_id(source)
        title = title_hint or self._get_video_title(source)

        metadata: dict = {"video_id": video_id}
        if title:
            metadata["Title"] = title

        # Try tiers in order
        for tier_num, tier_fn in [
            (1, lambda: self._tier1_transcript_api(video_id)),
            (2, lambda: self._tier2_ytdlp_subs(source)),
            (3, lambda: self._tier3_whisper(source)),
        ]:
            text = tier_fn()
            if text:
                metadata["extraction_tier"] = tier_num
                return ExtractionResult(
                    text=text,
                    source=source,
                    source_type="youtube",
                    extractor_name=self.__class__.__name__,
                    metadata=metadata,
                )

        raise ExtractionError(
            f"All extraction tiers failed for YouTube video: {source}",
            source=source,
        )
