"""YouTubeExtractor — 3-tier fallback with circuit breaker."""

from __future__ import annotations

import logging
import re
import tempfile
from typing import ClassVar

from ..core.base import BaseExtractor, ExtractionError, ExtractionResult

logger = logging.getLogger(__name__)


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

    def __init__(self, languages: list[str] | None = None, enable_whisper: bool = True):
        self.languages = languages or ["en", "ru"]
        self.enable_whisper = enable_whisper

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
            with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                return info.get("title", "")
        except Exception:
            return ""

    def _tier1_transcript_api(self, video_id: str) -> str | None:
        """Tier 1: youtube-transcript-api."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError:
            logger.debug("youtube-transcript-api not installed, skipping tier 1")
            return None

        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Try manual transcripts first
            for lang in self.languages:
                try:
                    transcript = transcript_list.find_manually_created_transcript([lang])
                    entries = transcript.fetch()
                    text = " ".join(e.text for e in entries)
                    logger.info("Tier 1 (manual subs, %s): success", lang)
                    return text
                except Exception:
                    continue

            # Try auto-generated
            for lang in self.languages:
                try:
                    transcript = transcript_list.find_generated_transcript([lang])
                    entries = transcript.fetch()
                    text = " ".join(e.text for e in entries)
                    logger.info("Tier 1 (auto subs, %s): success", lang)
                    return text
                except Exception:
                    continue

            # Try any available transcript
            try:
                for transcript in transcript_list:
                    entries = transcript.fetch()
                    text = " ".join(e.text for e in entries)
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
                opts = {
                    "writesubtitles": True,
                    "writeautomaticsub": True,
                    "subtitleslangs": self.languages,
                    "subtitlesformat": "json3/vtt/srt",
                    "skip_download": True,
                    "quiet": True,
                    "outtmpl": f"{tmp_dir}/%(id)s.%(ext)s",
                }

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

    def _tier3_whisper(self, url: str) -> str | None:
        """Tier 3: Download audio and transcribe with Whisper."""
        if not self.enable_whisper:
            logger.debug("Whisper disabled, skipping tier 3")
            return None

        try:
            import whisper
            import yt_dlp
        except ImportError:
            logger.debug("whisper/yt-dlp not installed, skipping tier 3")
            return None

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                audio_path = f"{tmp_dir}/audio.mp3"
                opts = {
                    "format": "bestaudio/best",
                    "outtmpl": audio_path,
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                    }],
                    "quiet": True,
                }

                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])

                # Find the audio file (yt-dlp may add extension)
                import glob
                audio_files = glob.glob(f"{tmp_dir}/audio*")
                if not audio_files:
                    return None

                logger.info("Tier 3: transcribing with Whisper...")
                model = whisper.load_model("base")
                result = model.transcribe(audio_files[0])
                text = result.get("text", "")

                if text:
                    logger.info("Tier 3 (Whisper): success")
                    return text

        except Exception as e:
            logger.debug("Tier 3 failed: %s", e)

        return None

    def extract(self, source: str) -> ExtractionResult:
        video_id = self._extract_video_id(source)
        title = self._get_video_title(source)

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
