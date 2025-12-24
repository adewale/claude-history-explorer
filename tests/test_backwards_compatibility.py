"""
Backwards Compatibility Tests for Wrapped URL Encoding

These tests ensure that previously generated URLs continue to decode correctly
as we make changes to the encoder/decoder. This prevents breaking changes
that would make old URLs unusable.

The golden files contain:
1. Known good encoded URLs from various time periods
2. Expected core values that must remain stable
3. Expected array lengths/structure that must be preserved

Run with: pytest tests/test_backwards_compatibility.py -v
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from claude_history_explorer.history import decode_wrapped_story_v3

# Get paths relative to this file
TESTS_DIR = Path(__file__).parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
PROJECT_ROOT = TESTS_DIR.parent
WRAPPED_WEBSITE_DIR = PROJECT_ROOT / "wrapped-website"
GOLDEN_FILE = FIXTURES_DIR / "golden_urls.json"


def load_golden_urls():
    """Load the golden URL test cases."""
    if not GOLDEN_FILE.exists():
        pytest.skip(f"Golden file not found: {GOLDEN_FILE}")

    with open(GOLDEN_FILE) as f:
        return json.load(f)


class TestPythonBackwardsCompatibility:
    """Test that Python decoder can decode all golden URLs."""

    @pytest.fixture
    def golden_urls(self):
        return load_golden_urls()

    def test_golden_urls_exist(self, golden_urls):
        """Verify golden URLs file is not empty."""
        assert len(golden_urls) >= 2, "Expected at least 2 golden URL test cases"

    @pytest.mark.parametrize("case_id", ["sample_demo_user", "real_user_dec_2025"])
    def test_decode_golden_url(self, golden_urls, case_id):
        """Test that each golden URL decodes successfully."""
        case = next((c for c in golden_urls if c["id"] == case_id), None)
        assert case is not None, f"Golden URL case '{case_id}' not found"

        # Decode should not raise
        story = decode_wrapped_story_v3(case["encoded"])

        # Verify version (using attribute access for dataclass)
        assert story.v == 3, "Decoded story must be V3"

    @pytest.mark.parametrize("case_id", ["sample_demo_user", "real_user_dec_2025"])
    def test_core_fields_match(self, golden_urls, case_id):
        """Test that core fields match expected values."""
        case = next((c for c in golden_urls if c["id"] == case_id), None)
        assert case is not None

        story = decode_wrapped_story_v3(case["encoded"])
        expected = case["expected_core"]

        for key, expected_value in expected.items():
            actual_value = getattr(story, key)
            assert actual_value == expected_value, (
                f"Core field '{key}' mismatch for {case_id}: "
                f"expected {expected_value}, got {actual_value}"
            )

    @pytest.mark.parametrize("case_id", ["sample_demo_user", "real_user_dec_2025"])
    def test_array_lengths(self, golden_urls, case_id):
        """Test that arrays have expected lengths."""
        case = next((c for c in golden_urls if c["id"] == case_id), None)
        assert case is not None

        story = decode_wrapped_story_v3(case["encoded"])
        expected = case["expected_arrays"]

        # Check exact lengths (using attribute access)
        if "hm_length" in expected:
            assert len(story.hm) == expected["hm_length"], "Heatmap must have 168 elements"
        if "ma_length" in expected:
            assert len(story.ma) == expected["ma_length"], "Monthly activity must have 12 elements"
        if "mh_length" in expected:
            assert len(story.mh) == expected["mh_length"], "Monthly hours must have 12 elements"
        if "ms_length" in expected:
            assert len(story.ms) == expected["ms_length"], "Monthly sessions must have 12 elements"
        if "ar_length" in expected:
            assert len(story.ar) == expected["ar_length"], "Agent ratio must have 10 elements"
        if "sk_length" in expected:
            assert len(story.sk) == expected["sk_length"], "Streaks must have 4 elements"

        # Check minimum lengths (for variable-length arrays)
        if "tp_min_length" in expected:
            assert len(story.tp) >= expected["tp_min_length"], "Too few projects"
        if "pc_min_length" in expected:
            assert len(story.pc) >= expected["pc_min_length"], "Too few co-occurrences"
        if "te_min_length" in expected:
            assert len(story.te) >= expected["te_min_length"], "Too few timeline events"
        if "sf_min_length" in expected:
            assert len(story.sf) >= expected["sf_min_length"], "Too few session fingerprints"

    @pytest.mark.parametrize("case_id", ["sample_demo_user", "real_user_dec_2025"])
    def test_first_project_structure(self, golden_urls, case_id):
        """Test that the first project has expected structure and values."""
        case = next((c for c in golden_urls if c["id"] == case_id), None)
        assert case is not None

        story = decode_wrapped_story_v3(case["encoded"])
        expected = case.get("expected_first_project", {})

        if not expected:
            pytest.skip("No expected_first_project defined")

        assert len(story.tp) > 0, "Expected at least one project"
        first_project = story.tp[0]

        # Projects are stored as lists: [name, messages, hours, days, sessions, agent_ratio]
        assert isinstance(first_project, (list, tuple)), "Project should be a list/tuple"
        assert len(first_project) >= 3, "Project should have at least 3 elements"

        # Map field names to indices: n=0, m=1, h=2, d=3, s=4, ar=5
        field_indices = {"n": 0, "m": 1, "h": 2, "d": 3, "s": 4, "ar": 5}

        for key, expected_value in expected.items():
            if key in field_indices:
                idx = field_indices[key]
                if idx < len(first_project):
                    actual_value = first_project[idx]
                    assert actual_value == expected_value, (
                        f"First project field '{key}' mismatch: "
                        f"expected {expected_value}, got {actual_value}"
                    )

    @pytest.mark.parametrize("case_id", ["sample_demo_user", "real_user_dec_2025"])
    def test_token_stats_structure(self, golden_urls, case_id):
        """Test that token stats have expected structure."""
        case = next((c for c in golden_urls if c["id"] == case_id), None)
        assert case is not None

        story = decode_wrapped_story_v3(case["encoded"])
        expected = case.get("expected_tokens", {})

        if not expected:
            pytest.skip("No expected_tokens defined")

        # tk is a dict attribute
        tk = story.tk

        if "total" in expected:
            assert tk.get("total") == expected["total"], "Token total mismatch"

        if expected.get("has_models"):
            assert "models" in tk, "Token stats should have models"
            assert isinstance(tk["models"], dict), "Models should be a dict"


class TestTypeScriptBackwardsCompatibility:
    """Test that TypeScript decoder can decode all golden URLs."""

    def test_typescript_decodes_golden_urls(self):
        """Verify TypeScript decoder handles all golden URLs."""
        result = subprocess.run(
            ["npx", "tsx", "tests/backwards-compat.test.ts"],
            capture_output=True,
            text=True,
            cwd=WRAPPED_WEBSITE_DIR,
        )

        # Print output for debugging
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        assert result.returncode == 0, (
            f"TypeScript backwards compatibility test failed!\n"
            f"Output:\n{result.stdout}\n"
            f"Errors:\n{result.stderr}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
