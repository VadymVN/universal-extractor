"""CLI interface — argparse + interactive mode."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import Config
from .core.base import ExtractionError, ExtractionResult
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
        help="Input file, directory, or URL. Use '-' for stdin.",
    )
    parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory (default: ./output/). Use '-' for stdout.",
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
        "-f", "--format",
        choices=["md", "txt", "json"],
        default="md",
        help="Output format: md (default), txt, or json",
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

    output = input("Output directory [./output/]: ").strip()
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


def _read_stdin() -> str:
    """Read all content from stdin."""
    return sys.stdin.buffer.read().decode("utf-8")


def _handle_stdin() -> ExtractionResult:
    """Create ExtractionResult from stdin content."""
    text = _read_stdin()
    if not text.strip():
        raise ExtractionError("Empty input from stdin", source="stdin")
    return ExtractionResult(
        text=text,
        source="stdin",
        source_type="plaintext",
        extractor_name="stdin",
    )


def _render_result(result: ExtractionResult, fmt: str) -> str:
    """Render an ExtractionResult to a string for stdout output."""
    if fmt == "json":
        return result.to_json()
    if fmt == "txt":
        return result.to_header() + "\n\n" + result.text
    # md (default): prefer markdown_text if available
    body = result.markdown_text or result.text
    return result.to_header() + "\n\n" + body


def _is_stdin_mode(args: argparse.Namespace) -> bool:
    """Check if we should read from stdin."""
    return args.input == "-" or (args.input is None and not sys.stdin.isatty())


def _is_stdout_mode(args: argparse.Namespace) -> bool:
    """Check if we should write to stdout."""
    return args.output == "-"


def _status(msg: str, stdout_mode: bool) -> None:
    """Print a status message to stderr when in stdout mode, else to stdout."""
    if stdout_mode:
        print(msg, file=sys.stderr)
    else:
        print(msg)


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

    stdin_mode = _is_stdin_mode(args)
    stdout_mode = _is_stdout_mode(args)

    # Build registry and router
    registry = ExtractorRegistry()
    register_all(registry)
    router = InputRouter(registry)

    writer = None
    if not stdout_mode:
        writer = OutputWriter(args.output, fmt=args.format)

    report = BatchReport()

    # Stdin mode
    if stdin_mode:
        try:
            result = _handle_stdin()
        except ExtractionError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        if stdout_mode:
            sys.stdout.write(_render_result(result, args.format))
        else:
            assert writer is not None
            path = writer.write(result)
            _status(f"Extracted: {result.source}", stdout_mode)
            _status(f"Type: {result.source_type} | Characters: {result.char_count:,}", stdout_mode)
            _status(f"Saved to: {path}", stdout_mode)
        return 0

    source = args.input

    # Interactive mode if no input and stdin is a TTY
    if not source:
        source, output_dir = interactive_mode(config)
        writer = OutputWriter(output_dir, fmt=args.format)

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
                err_result = ExtractionResult(
                    text="", source=str(file_path), source_type="unknown",
                    extractor_name="none", error=str(e),
                )
                results.append(err_result)
                report.add(err_result)

        if stdout_mode:
            for result in results:
                if result.error and not result.text:
                    continue
                sys.stdout.write(_render_result(result, args.format) + "\n")
        else:
            assert writer is not None
            writer.write_batch(results)
        _status(f"\n{report.summary()}", stdout_mode)
        if not stdout_mode and writer:
            _status(f"\nOutput: {writer.output_dir}", stdout_mode)
    else:
        # Single file or URL
        try:
            result = router.extract(source)
            if stdout_mode:
                sys.stdout.write(_render_result(result, args.format))
            else:
                assert writer is not None
                path = writer.write(result)
                _status(f"Saved to: {path}", stdout_mode)
            _status(f"Extracted: {result.source}", stdout_mode)
            _status(
                f"Type: {result.source_type} | Characters: {result.char_count:,}",
                stdout_mode,
            )
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
