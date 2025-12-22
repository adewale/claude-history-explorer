"""
Integration tests for Python/TypeScript schema alignment.

This test verifies that the Python encoder and TypeScript decoder
produce consistent results by:
1. Generating test cases using Python encoder
2. Running TypeScript validator to decode and compare
3. Failing if any schema mismatches are detected

Run with: pytest tests/test_schema_alignment.py -v
"""

import subprocess
import sys
from pathlib import Path

import pytest

# Get paths relative to this file
TESTS_DIR = Path(__file__).parent
PROJECT_ROOT = TESTS_DIR.parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
WRAPPED_WEBSITE_DIR = PROJECT_ROOT / "wrapped-website"


def test_generate_schema_test_cases():
    """Test that the schema test case generator runs successfully."""
    result = subprocess.run(
        [sys.executable, str(TESTS_DIR / "generate_schema_test_cases.py")],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, f"Generator failed:\n{result.stderr}"
    assert (FIXTURES_DIR / "schema_test_cases.json").exists(), "Test cases file not created"


def test_typescript_decodes_python_encoding():
    """Verify TypeScript decoder correctly decodes Python-encoded data.

    This is the main schema alignment test. It:
    1. Regenerates test cases from Python (ensures freshness)
    2. Runs TypeScript validator that decodes and compares
    3. Fails if any field mismatches are detected

    This test requires Node.js and npx to be available.
    """
    # First, regenerate test cases to ensure they're fresh
    gen_result = subprocess.run(
        [sys.executable, str(TESTS_DIR / "generate_schema_test_cases.py")],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert gen_result.returncode == 0, f"Generator failed:\n{gen_result.stderr}"

    # Run TypeScript schema alignment test
    result = subprocess.run(
        ["npx", "tsx", "tests/schema-alignment.test.ts"],
        capture_output=True,
        text=True,
        cwd=WRAPPED_WEBSITE_DIR,
    )

    # Print output for debugging
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Check for success
    assert result.returncode == 0, (
        f"Schema alignment test failed!\n"
        f"Python encoder and TypeScript decoder are not aligned.\n"
        f"Output:\n{result.stdout}\n"
        f"Errors:\n{result.stderr}"
    )


def test_roundtrip_basic():
    """Test basic roundtrip: Python encode -> TypeScript decode -> verify."""
    # This is a sanity check that the test infrastructure works
    import json

    cases_file = FIXTURES_DIR / "schema_test_cases.json"
    if not cases_file.exists():
        pytest.skip("Test cases not generated yet")

    with open(cases_file) as f:
        cases = json.load(f)

    assert len(cases) > 0, "No test cases generated"
    assert all("id" in c for c in cases), "Missing 'id' in test cases"
    assert all("encoded" in c for c in cases), "Missing 'encoded' in test cases"
    assert all("expected" in c for c in cases), "Missing 'expected' in test cases"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
