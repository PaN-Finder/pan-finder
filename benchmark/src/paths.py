"""Common path utilities for the benchmark tools.

This centralises logic for resolving the project root so that it is defined
in exactly one place. Add further helpers here as needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Computed once at import time; using resolve() to remove symlinks.
_project_root = Path(__file__).resolve().parents[2]
_benchmark_dir = _project_root / "benchmark"


def root_dir() -> Path:
    """Return the repository root directory (project root)."""
    return _project_root


def benchmark_dir() -> Path:
    """Return the benchmark directory."""
    return _benchmark_dir


def include_server_modules():
    """Add server directory to Python path to make server modules importable."""
    server_dir = root_dir() / "server"
    if str(server_dir) not in sys.path:
        sys.path.insert(0, str(server_dir))


__all__ = ["root_dir", "benchmark_dir", "include_server_modules"]
