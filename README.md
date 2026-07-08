# Universal Extractor

Extract text from any file or URL — PDF, DOCX, PPTX, XLSX, video/audio, YouTube, web pages.

A single, extensible tool that replaces per-project extraction scripts with a unified CLI and Python library.

## Features

- **PDF** extraction via pdfplumber
- **DOCX** extraction via python-docx
- **PPTX** extraction via python-pptx (slides, tables, bullet lists)
- **XLSX** extraction via openpyxl (multiple sheets, tables)
- **Plain text** with automatic encoding detection (UTF-8 → chardet → latin-1)
- **Web pages** via trafilatura
- **YouTube** transcripts with 3-tier fallback (transcript API → yt-dlp subs → Whisper)
- **YouTube playlists** — transcribe all videos from a playlist into a named subdirectory
- **Video/Audio** transcription via faster-whisper (CTranslate2; CPU int8, CUDA float16 when available)
- **Pipe support** — read from stdin (`-i -`) and write to stdout (`-o -`)
- YAML-style metadata headers in output files
- Batch processing with progress bars — directory and playlist results saved to subdirectories
- Dry-run mode for previewing
- Graceful dependency degradation (missing whisper just disables video extraction)

## Installation

```bash
# Core (PDF, DOCX, text, web pages)
pip install -e .

# With video/audio support
pip install -e ".[video]"

# With dev tools
pip install -e ".[dev]"
```

## CLI Usage

```bash
# Single file
uniextract -i document.pdf

# Directory (recursive)
uniextract -i ./documents/ -o ./results/

# YouTube video
uniextract -i "https://youtube.com/watch?v=dQw4w9WgXcQ"

# YouTube playlist (all videos → output/Playlist_Name/)
uniextract -i "https://youtube.com/playlist?list=PLxxxxxxx"

# Private playlist (use browser cookies)
uniextract -i "https://youtube.com/playlist?list=PLxxxxxxx" --cookies chrome

# Large playlist via rotating proxy (avoids YouTube IP blocks / IpBlocked)
uniextract -i "https://youtube.com/playlist?list=PLxxxxxxx" --proxy "http://user:pass@proxy-host:port"

# Web page
uniextract -i "https://example.com/article"

# Preview without processing
uniextract --dry-run -i ./documents/

# List available extractors
uniextract --list-extractors

# Interactive mode (prompts for input)
uniextract

# Pipe support (stdin/stdout)
echo "some text" | uniextract -i - -o - -f txt
echo "some text" | uniextract -i - -o - -f json
uniextract -i document.pdf -o -
cat document.txt | uniextract -o -
```

### Options

| Flag | Description |
|------|-------------|
| `-i, --input` | Input file, directory, or URL. Use `-` for stdin |
| `-o, --output` | Output directory (default: `./output/`). Use `-` for stdout |
| `-f, --format` | Output format: `md` (default), `txt`, `json` |
| `-b, --batch` | Force batch mode for directory input |
| `--whisper-model` | Whisper model: tiny, base, small, medium, large |
| `--language` | Language hint for transcription |
| `--no-whisper` | Disable Whisper (skip video/audio) |
| `--cookies [BROWSER]` | Use browser cookies for private playlists (auto-detect or specify: chrome, firefox, safari) |
| `--proxy URL` | Route YouTube requests through a rotating proxy to avoid IP blocks. Overrides `UNIEXTRACT_PROXY_URL` |
| `--dry-run` | Preview what would be processed |
| `--list-extractors` | Show available extractors |
| `-v, --verbose` | Enable debug logging |

## Python API

```python
from universal_extractor import extract, extract_batch, extract_playlist, save_result

# Single file
result = extract("document.pdf")
print(result.text)
print(result.char_count)

# Batch (directory)
results = extract_batch("./documents/")
for r in results:
    print(f"{r.source}: {r.char_count} chars")

# YouTube playlist
title, results = extract_playlist("https://youtube.com/playlist?list=PLxxxxxxx")
print(f"Playlist: {title}, {len(results)} videos")

# Save with metadata header (default: markdown)
save_result(result, "output/")

# Save as plain text or JSON
save_result(result, "output/", fmt="txt")
save_result(result, "output/", fmt="json")

# Custom config
from universal_extractor import Config
result = extract("video.mp4", config=Config(whisper_model="medium"))
```

## Output Format

Default output is **Markdown** (`.md`). Use `--format txt` or `--format json` for alternatives.

Extractors that support rich formatting (web pages, DOCX, PDF with tables) produce Markdown natively. Others fall back to plain text.

```bash
# Markdown (default)
uniextract -i document.pdf

# Plain text
uniextract -i document.pdf --format txt

# JSON
uniextract -i document.pdf --format json
```

Markdown and text files include a YAML frontmatter header:

```
---
Source: /path/to/document.pdf
Type: pdf
Extracted: 2026-03-04T10:30:00
Language: en
Characters: 15432
Pages: 12
Author: John Doe
---

[extracted content here]
```

## Output Structure

Single file or URL extraction saves directly to the output directory. Batch (directory) and playlist extraction create a **named subdirectory**:

```
# Single file → output/document.md
uniextract -i document.pdf -o output/

# Directory → output/<dir_name>/file1.md, file2.md, ...
uniextract -i ./lectures/ -o output/

# Playlist → output/<Playlist_Title>/<Video_Title>.md, ...
uniextract -i "https://youtube.com/playlist?list=PLxxx" -o output/
```

Output files from YouTube are named by **video title** (e.g. `How_to_Learn_Chess.md`).

**Re-run safety:** playlist extraction skips videos whose output files already exist, so you can safely re-run after interruptions or failures without re-downloading.

## Configuration

Settings can be passed via constructor, environment variables, or defaults:

| Env Variable | Default | Description |
|---|---|---|
| `UNIEXTRACT_WHISPER_MODEL` | `base` | Whisper model size |
| `UNIEXTRACT_WHISPER_LANGUAGE` | auto | Language hint |
| `UNIEXTRACT_ENABLE_WHISPER` | `true` | Enable Whisper |
| `UNIEXTRACT_YOUTUBE_LANGUAGES` | `en,ru` | Comma-separated language list |
| `UNIEXTRACT_WEB_TIMEOUT` | `30` | Web request timeout (seconds) |
| `UNIEXTRACT_MAX_WORKERS` | `4` | Max parallel workers |
| `UNIEXTRACT_LOG_LEVEL` | `INFO` | Logging level |
| `UNIEXTRACT_OUTPUT_DIR` | `output` | Default output directory |
| `UNIEXTRACT_OUTPUT_FORMAT` | `md` | Output format: `md`, `txt`, `json` |
| `UNIEXTRACT_PROXY_URL` | _(none)_ | Rotating proxy URL for YouTube (e.g. `http://user:pass@host:port`). Avoids IP blocks; can live in `.env` |

## Avoiding YouTube IP Blocks

When transcribing large playlists, YouTube may rate-limit or block your IP
(`IpBlocked` / HTTP 429) after a number of transcript requests. Each video costs two
requests to YouTube's `timedtext`/InnerTube endpoints, so a single static IP — VPN,
datacenter, **or even a home residential IP** — accumulates enough requests to get
flagged. VPN and datacenter IPs are blocked fastest.

The robust fix is a **rotating residential proxy**: every request exits from a different
residential IP, so no single IP accumulates enough requests to be blocked.

### Setup

1. Get a rotating residential proxy from any provider (e.g.
   [IPRoyal](https://iproyal.com), [Webshare](https://www.webshare.io)). A small
   pay-as-you-go plan is plenty — transcripts are text, so ~1 GB covers thousands of
   videos.
2. Point the extractor at it, per-run or persistently:

   ```bash
   # per run
   uniextract -i "<playlist-url>" --proxy "http://user:pass@proxy-host:port"

   # or persistently via .env (auto-loaded; keep it out of git)
   echo 'UNIEXTRACT_PROXY_URL=http://user:pass@proxy-host:port' >> .env
   ```

### Behavior when a proxy is set

- Only the transcript fetch (Tier 1) is proxied — playlist metadata still uses the direct
  connection (it isn't the part that gets blocked).
- Transient per-IP failures (e.g. Google's "sorry" bot-wall) are retried automatically on
  a fresh rotation IP.
- The inter-video delay drops from 15 s to ~1 s, since rotation removes the need to
  throttle a single IP.
- Without a proxy, behavior is unchanged.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev,video]"

# Run tests
make test

# Lint
make lint

# Format
make format
```

## Adding a New Extractor

1. Create `src/universal_extractor/extractors/myformat.py`
2. Subclass `BaseExtractor`, set `supported_extensions` and `required_packages`
3. Implement `extract(source) -> ExtractionResult`
4. Register in `extractors/__init__.py`

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

MIT
