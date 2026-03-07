"""Integration tests for the CLI."""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"


def run_cli(*args: str, stdin_data: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "universal_extractor", *args],
        input=stdin_data,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )


class TestCLI:
    def test_help(self):
        result = run_cli("--help")
        assert result.returncode == 0
        assert "Universal Text Extractor" in result.stdout

    def test_list_extractors(self):
        result = run_cli("--list-extractors")
        assert result.returncode == 0
        assert "PlainTextExtractor" in result.stdout

    def test_extract_single_file(self, tmp_path):
        result = run_cli("-i", str(FIXTURES / "sample.txt"), "-o", str(tmp_path))
        assert result.returncode == 0
        assert "Extracted:" in result.stdout
        # Default format is now .md
        output_files = list(tmp_path.glob("*.md"))
        assert len(output_files) == 1
        content = output_files[0].read_text()
        assert "sample text file" in content

    def test_extract_directory(self, tmp_path):
        result = run_cli("-i", str(FIXTURES), "-o", str(tmp_path))
        assert result.returncode == 0
        assert "Processed:" in result.stdout
        # Batch now writes into a subdirectory named after the input dir
        output_files = list(tmp_path.rglob("*.md"))
        assert len(output_files) >= 2  # sample.txt and sample.md at minimum

    def test_extract_txt_format(self, tmp_path):
        result = run_cli(
            "-i", str(FIXTURES / "sample.txt"), "-o", str(tmp_path), "--format", "txt"
        )
        assert result.returncode == 0
        output_files = list(tmp_path.glob("*.txt"))
        assert len(output_files) == 1
        content = output_files[0].read_text()
        assert content.startswith("---")

    def test_extract_json_format(self, tmp_path):
        result = run_cli(
            "-i", str(FIXTURES / "sample.txt"), "-o", str(tmp_path), "--format", "json"
        )
        assert result.returncode == 0
        output_files = list(tmp_path.glob("*.json"))
        assert len(output_files) == 1
        data = json.loads(output_files[0].read_text())
        assert "text" in data
        assert "source" in data

    def test_dry_run(self):
        result = run_cli("--dry-run", "-i", str(FIXTURES))
        assert result.returncode == 0
        assert "sample.txt" in result.stdout

    def test_nonexistent_input(self):
        result = run_cli("-i", "/nonexistent/file.txt")
        assert result.returncode == 1

    def test_python_api(self):
        """Test the public Python API."""
        result = subprocess.run(
            [
                sys.executable, "-c",
                "from universal_extractor import extract; "
                f"r = extract('{FIXTURES / 'sample.txt'}'); "
                "print(r.text[:30])"
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "sample text" in result.stdout.lower()

    def test_stdin_to_stdout(self):
        """Pipe stdin to stdout."""
        result = run_cli("-i", "-", "-o", "-", "-f", "txt", stdin_data="piped text")
        assert result.returncode == 0
        assert "piped text" in result.stdout

    def test_file_to_stdout(self):
        """Read from file, write to stdout."""
        result = run_cli("-i", str(FIXTURES / "sample.txt"), "-o", "-")
        assert result.returncode == 0
        assert "sample" in result.stdout.lower()
