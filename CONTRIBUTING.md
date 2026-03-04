# Contributing to Universal Extractor

## Development Setup

```bash
git clone https://github.com/VadymVN/universal-extractor.git
cd universal-extractor
pip install -e ".[dev,video]"
```

## Running Tests

```bash
make test          # Run all tests
make test-cov      # Run with coverage
make lint          # Run linter + type checker
```

## Adding a New Extractor

### 1. Create the extractor module

Create `src/universal_extractor/extractors/myformat.py`:

```python
from __future__ import annotations
from typing import ClassVar
from ..core.base import BaseExtractor, ExtractionError, ExtractionResult


class MyFormatExtractor(BaseExtractor):
    supported_extensions: ClassVar[set[str]] = {".myf"}
    required_packages: ClassVar[set[str]] = {"myformat-lib"}

    def extract(self, source: str) -> ExtractionResult:
        import myformat_lib

        text = myformat_lib.read(source)

        return ExtractionResult(
            text=text,
            source=source,
            source_type="myformat",
            extractor_name=self.__class__.__name__,
        )
```

### 2. Register it

In `src/universal_extractor/extractors/__init__.py`, add:

```python
try:
    from .myformat import MyFormatExtractor
    registry.register(MyFormatExtractor())
except ImportError:
    logger.debug("MyFormatExtractor unavailable")
```

### 3. Add tests

Create `tests/unit/extractors/test_myformat.py` with mock-based tests.

### 4. Add optional dependency

In `pyproject.toml`, add to the appropriate extras group.

## Code Style

- Python 3.11+, type hints everywhere
- `ruff` for linting and formatting
- `mypy` for type checking
- All code and docs in English
- Keep extractors self-contained — each should work independently

## Pull Request Process

1. Create a feature branch from `main`
2. Add tests for new functionality
3. Ensure `make test` and `make lint` pass
4. Submit a PR with a clear description
