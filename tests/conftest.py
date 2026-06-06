"""Test configuration and fixtures for claude-history-explorer."""

import os
import shutil
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent
WRAPPED_WEBSITE_DIR = PROJECT_ROOT / "wrapped-website"


def require_wrapped_node_deps() -> None:
    """Require TypeScript bridge dependencies, failing in CI and skipping locally."""
    if not (WRAPPED_WEBSITE_DIR / "node_modules" / "tsx").exists():
        message = "Run `npm ci` in wrapped-website before TypeScript bridge tests"
        if os.environ.get("CI"):
            pytest.fail(message)
        pytest.skip(message)


def npx_command() -> str:
    """Return a Windows-safe npx executable path for subprocess calls."""
    executable = shutil.which("npx.cmd" if os.name == "nt" else "npx") or shutil.which("npx")
    if executable:
        return executable
    message = "npx not found; install Node.js before running TypeScript bridge tests"
    if os.environ.get("CI"):
        pytest.fail(message)
    pytest.skip(message)


def pytest_configure():
    """Configure pytest for our tests."""
    pass
