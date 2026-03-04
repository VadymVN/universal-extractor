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
- **Video/Audio** transcription via OpenAI Whisper (MPS/CUDA/CPU auto-detection)
- **Pipe support** — read from stdin (`-i -`) and write to stdout (`-o -`)
- YAML-style metadata headers in output files
- Batch processing with progress bars
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
| `--dry-run` | Preview what would be processed |
| `--list-extractors` | Show available extractors |
| `-v, --verbose` | Enable debug logging |

## Python API

```python
from universal_extractor import extract, extract_batch, save_result

# Single file
result = extract("document.pdf")
print(result.text)
print(result.char_count)

# Batch
results = extract_batch("./documents/")
for r in results:
    print(f"{r.source}: {r.char_count} chars")

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
