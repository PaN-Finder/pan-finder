"""Common path utilities for the benchmark tools.

This centralises logic for resolving the project root so that it is defined
in exactly one place. Add further helpers here as needed.
"""

from __future__ import annotations

from pathlib import Path

# Computed once at import time; using resolve() to remove symlinks.
_project_root = Path(__file__).resolve().parents[2]
_benchmark_dir = _project_root / "benchmark"


def root_dir() -> Path:
    """Return the repository root directory (project root)."""
    return _project_root


def project_root() -> Path:  # alias for readability in some contexts
    return _project_root


def benchmark_dir() -> Path:
    """Return the benchmark directory."""
    return _benchmark_dir


__all__ = ["root_dir", "project_root", "benchmark_dir"]
