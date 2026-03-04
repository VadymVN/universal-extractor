"""CLI interface — argparse + interactive mode."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import Config
from .core.base import ExtractionError
from .core.registry import ExtractorRegistry
from .core.router import InputRouter
from .extractors import register_all
from .output.report import BatchReport
from .output.writer import OutputWriter
from .utils.logging import setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uniextract",
        description="Universal Text Extractor — extract text from any file or URL",
    )
    parser.add_argument(
        "-i", "--input",
        help="Input file, directory, or URL",
    )
    parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory (default: ./output/)",
    )
    parser.add_argument(
        "-b", "--batch",
        action="store_true",
        help="Process input as a directory of files",
    )
    parser.add_argument(
        "--whisper-model",
        default=None,
        help="Whisper model size: tiny, base, small, medium, large",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Language hint for transcription",
    )
    parser.add_argument(
        "--no-whisper",
        action="store_true",
        help="Disable Whisper (skip video/audio extraction)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be processed without extracting",
    )
    parser.add_argument(
        "--list-extractors",
        action="store_true",
        help="List all available extractors and exit",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser


def interactive_mode(config: Config) -> tuple[str, str]:
    """Prompt user for input and output when no arguments given."""
    print("Universal Text Extractor — Interactive Mode")
    print("=" * 45)

    source = input("\nEnter file path, directory, or URL: ").strip()
    if not source:
        print("No input provided. Exiting.")
        sys.exit(0)

    output = input(f"Output directory [./output/]: ").strip()
    if not output:
        output = "output"

    return source, output


def list_extractors() -> None:
    """Print all available extractors."""
    registry = ExtractorRegistry()
    register_all(registry)

    print("Available extractors:")
    print("-" * 50)
    for info in registry.list_extractors():
        exts = ", ".join(sorted(info["extensions"])) if info["extensions"] else "—"
        urls = ", ".join(sorted(info["url_patterns"])) if info["url_patterns"] else "—"
        print(f"  {info['name']}")
        print(f"    Extensions: {exts}")
        print(f"    URL patterns: {urls}")
        print()


def dry_run(source: str, registry: ExtractorRegistry) -> None:
    """Preview what would be processed."""
    from .utils.sanitize import is_url

    if is_url(source):
        ext = registry.get_for_url(source)
        status = ext.__class__.__name__ if ext else "NO EXTRACTOR"
        print(f"  [URL] {source} -> {status}")
        return

    path = Path(source)
    if path.is_file():
        ext = registry.get(source)
        status = ext.__class__.__name__ if ext else "SKIPPED (no extractor)"
        print(f"  {source} -> {status}")
        return

    if path.is_dir():
        print(f"Scanning directory: {source}")
        for f in sorted(path.rglob("*")):
            if not f.is_file():
                continue
            ext = registry.get(str(f))
            status = ext.__class__.__name__ if ext else "SKIP"
            marker = "+" if ext else "-"
            print(f"  [{marker}] {f.relative_to(path)} -> {status}")
        return

    print(f"  Source not found: {source}")


def run(args: argparse.Namespace) -> int:
    """Main execution logic."""
    config_kwargs = {}
    if args.whisper_model:
        config_kwargs["whisper_model"] = args.whisper_model
    if args.language:
        config_kwargs["whisper_language"] = args.language
    if args.no_whisper:
        config_kwargs["enable_whisper"] = False

    config = Config.from_env(**config_kwargs)

    log_level = "DEBUG" if args.verbose else config.log_level
    setup_logging(log_level)

    # Build registry and router
    registry = ExtractorRegistry()
    register_all(registry)
    router = InputRouter(registry)
    writer = OutputWriter(args.output)
    report = BatchReport()

    source = args.input

    # Interactive mode if no input
    if not source:
        source, output_dir = interactive_mode(config)
        writer = OutputWriter(output_dir)

    # Dry run
    if args.dry_run:
        dry_run(source, registry)
        return 0

    # Classify input
    try:
        input_type = router.classify(source)
    except ExtractionError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Process
    if input_type == "directory" or args.batch:
        from tqdm import tqdm
        results = []
        dir_path = Path(source)
        files = [f for f in sorted(dir_path.rglob("*")) if f.is_file() and registry.get(str(f))]

        for file_path in tqdm(files, desc="Extracting", unit="file"):
            try:
                result = router.extract(str(file_path))
                results.append(result)
                report.add(result)
            except Exception as e:
                from .core.base import ExtractionResult
                err_result = ExtractionResult(
                    text="", source=str(file_path), source_type="unknown",
                    extractor_name="none", error=str(e),
                )
                results.append(err_result)
                report.add(err_result)

        paths = writer.write_batch(results)
        print(f"\n{report.summary()}")
        print(f"\nOutput: {writer.output_dir}")
    else:
        # Single file or URL
        try:
            result = router.extract(source)
            path = writer.write(result)
            print(f"Extracted: {result.source}")
            print(f"Type: {result.source_type} | Characters: {result.char_count:,}")
            print(f"Saved to: {path}")
        except ExtractionError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    return 0


def main() -> None:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.list_extractors:
        list_extractors()
        sys.exit(0)

    sys.exit(run(args))
