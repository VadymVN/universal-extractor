"""Shared test fixtures."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def sample_txt(fixtures_dir: Path) -> Path:
    return fixtures_dir / "sample.txt"


@pytest.fixture
def sample_md(fixtures_dir: Path) -> Path:
    return fixtures_dir / "sample.md"
