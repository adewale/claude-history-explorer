"""Test configuration and fixtures for claude-history-explorer."""

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent
WRAPPED_WEBSITE_DIR = PROJECT_ROOT / "wrapped-website"


def require_wrapped_node_deps() -> None:
    """Skip TypeScript bridge tests until wrapped-website dependencies are installed."""
    if not (WRAPPED_WEBSITE_DIR / "node_modules" / "tsx").exists():
        pytest.skip("Run `npm ci` in wrapped-website before TypeScript bridge tests")


def pytest_configure():
    """Configure pytest for our tests."""
    pass
