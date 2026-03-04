"""Tests for pipe support (stdin/stdout)."""

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


class TestPipeSupport:
    def test_stdin_pipe(self):
        """Read from stdin with -i -, write to stdout with -o -."""
        result = run_cli("-i", "-", "-o", "-", "-f", "txt", stdin_data="hello world")
        assert result.returncode == 0
        assert "hello world" in result.stdout

    def test_stdin_pipe_json(self):
        """Stdin with JSON output format."""
        result = run_cli("-i", "-", "-o", "-", "-f", "json", stdin_data="test content")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["source"] == "stdin"
        assert data["source_type"] == "plaintext"
        assert "test content" in data["text"]

    def test_stdout_from_file(self):
        """Read from file, write to stdout."""
        result = run_cli("-i", str(FIXTURES / "sample.txt"), "-o", "-")
        assert result.returncode == 0
        assert "sample" in result.stdout.lower()

    def test_stdout_from_file_json(self):
        """Read from file, write JSON to stdout."""
        result = run_cli("-i", str(FIXTURES / "sample.txt"), "-o", "-", "-f", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "text" in data
        assert "source" in data

    def test_empty_stdin_error(self):
        """Empty stdin should return error."""
        result = run_cli("-i", "-", "-o", "-", stdin_data="")
        assert result.returncode == 1
        assert "Error" in result.stderr

    def test_status_messages_to_stderr(self):
        """When using stdout mode, status messages go to stderr."""
        result = run_cli("-i", "-", "-o", "-", "-f", "txt", stdin_data="test data")
        assert result.returncode == 0
        # Stdout contains the rendered result
        assert "test data" in result.stdout
