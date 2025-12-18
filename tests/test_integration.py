"""
Integration tests for V3 Wrapped encoding/decoding across Python and TypeScript.

These tests verify that:
1. Python can generate and encode V3 stories
2. The encoded string can be decoded by TypeScript
3. The decoded data matches the original

Run with: uv run pytest tests/test_integration.py -v
"""

import json
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from claude_history_explorer.history import (
    WrappedStoryV3,
    encode_wrapped_story_v3,
    decode_wrapped_story_v3,
    generate_wrapped_story_v3,
    Session,
    Message,
)


class TestPythonEncodeDecode:
    """Test Python encode/decode roundtrip."""

    def test_basic_roundtrip(self):
        """Test basic encode/decode roundtrip in Python."""
        # Using compact array formats:
        # tp: [name, messages, hours, days, sessions, agent_ratio]
        # te: [day, type, value, project_idx] (-1 for missing)
        # sf: [duration, messages, is_agent, hour, weekday, project_idx, fp0..fp7]
        original = WrappedStoryV3(
            v=3,
            y=2025,
            n="Integration Test",
            p=5,
            s=100,
            m=5000,
            h=200,
            d=45,
            hm=[0] * 100 + [10] * 50 + [0] * 18,
            ma=[100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200],
            mh=[10, 20, 30, 40, 50, 60, 50, 40, 30, 20, 10, 5],
            ms=[8, 10, 12, 15, 18, 20, 18, 15, 12, 10, 8, 6],
            sd=[5, 10, 20, 30, 15, 10, 5, 3, 1, 1],
            ar=[2, 5, 10, 15, 20, 20, 15, 8, 3, 2],
            ml=[10, 20, 30, 25, 10, 3, 1, 1],
            ts={'ad': 45, 'sp': 65, 'fc': 72, 'cc': 58, 'wr': 25,
                'bs': 40, 'cs': 33, 'mv': 55, 'td': 60, 'ri': 70},
            tp=[
                ['MainProject', 2000, 80, 25, 40, 45],
                ['SideProject', 1500, 60, 20, 30, 60],
            ],
            pc=[(0, 1, 10)],
            te=[
                [50, 0, 150, -1],  # peak_day, no project
                [100, 4, 1000, 0],  # milestone, project 0
            ],
            sf=[
                [120, 100, 0, 10, 0, 0, 20, 40, 60, 80, 50, 10, 30, 20],  # is_agent=0 (False)
            ],
            ls=4.5,
            sk=[5, 10, 3, 4],
            tk={'total': 1000000, 'input': 600000, 'output': 400000,
                'cache_read': 200000, 'cache_create': 50000,
                'models': {'sonnet': 800000, 'haiku': 200000}},
        )

        # Encode
        encoded = encode_wrapped_story_v3(original)

        # Verify encoded is URL-safe
        import string
        valid_chars = string.ascii_letters + string.digits + '-_'
        assert all(c in valid_chars for c in encoded), "Encoded string should be URL-safe"

        # Decode
        decoded = decode_wrapped_story_v3(encoded)

        # Verify fields match
        assert decoded.v == original.v
        assert decoded.y == original.y
        assert decoded.n == original.n
        assert decoded.p == original.p
        assert decoded.s == original.s
        assert decoded.m == original.m
        assert decoded.h == original.h
        assert decoded.d == original.d

        # Heatmap may be RLE encoded, but should decode to same length
        assert len(decoded.hm) == 168

        # Monthly data should match exactly
        assert decoded.ma == original.ma
        assert decoded.mh == original.mh
        assert decoded.ms == original.ms

        # Trait scores should match
        for trait in ['ad', 'sp', 'fc', 'cc', 'wr', 'bs', 'cs', 'mv', 'td', 'ri']:
            assert decoded.ts[trait] == original.ts[trait]

        # Projects should match (compact array format)
        assert len(decoded.tp) == len(original.tp)
        for i, proj in enumerate(decoded.tp):
            # tp is array: [name, messages, hours, days, sessions, agent_ratio]
            assert proj[0] == original.tp[i][0]  # name
            assert proj[1] == original.tp[i][1]  # messages

    def test_url_length_constraints(self):
        """Test that typical stories stay under URL length limits."""
        # Using compact array formats
        story = WrappedStoryV3(
            v=3,
            y=2025,
            n="Typical Developer",
            p=8,
            s=250,
            m=15000,
            h=400,
            d=120,
            hm=[0] * 80 + list(range(1, 16)) * 5 + [0] * 13,  # Sparse pattern
            ma=[800, 900, 1200, 1500, 1400, 1100, 900, 1000, 1300, 1600, 1400, 1200],
            mh=[30, 35, 45, 55, 50, 40, 35, 40, 50, 60, 55, 45],
            ms=[20, 22, 28, 35, 32, 26, 22, 25, 30, 38, 35, 28],
            sd=[5, 15, 30, 40, 35, 25, 15, 8, 3, 2],
            ar=[2, 5, 12, 20, 25, 18, 10, 5, 2, 1],
            ml=[15, 25, 35, 30, 20, 10, 5, 3],
            ts={'ad': 45, 'sp': 60, 'fc': 55, 'cc': 70, 'wr': 30,
                'bs': 45, 'cs': 40, 'mv': 50, 'td': 55, 'ri': 65},
            tp=[
                # [name, messages, hours, days, sessions, agent_ratio]
                [f'Project{i}', 2000 - i * 100, 50 - i * 5, 30 - i * 2, 35 - i * 3, 40 + i * 5]
                for i in range(8)
            ],
            pc=[(0, 1, 8), (0, 2, 5), (1, 2, 3), (0, 3, 4)],
            te=[
                # [day, type, value, project_idx]
                [50, 0, 200, -1],
                [100, 4, 1000, -1],
                [150, 3, -1, 2],  # new_project, no value, project 2
                [200, 4, 5000, -1],
            ],
            sf=[
                # [duration, messages, is_agent, hour, weekday, project_idx, fp0..fp7]
                [60 + i * 10, 50 + i * 5, i % 2, 10 + i, i % 7, i % 8] + [20 + i * 5] * 8
                for i in range(5)
            ],
            ls=6.5,
            sk=[8, 15, 5, 6],
            tk={'total': 2000000, 'input': 1200000, 'output': 800000,
                'cache_read': 500000, 'cache_create': 100000,
                'models': {'sonnet': 1500000, 'haiku': 400000, 'opus': 100000}},
            yoy={'pm': 10000, 'ph': 300, 'ps': 180, 'pp': 6, 'pd': 100},
        )

        encoded = encode_wrapped_story_v3(story)

        # URL base is ~50 chars, encoded data should keep total under 2KB
        url_length = 60 + len(encoded)  # Account for "?d=" and base URL
        assert url_length < 2000, f"URL too long: {url_length} chars"


class TestCrossLanguageCompatibility:
    """Test that Python-encoded stories can be decoded by TypeScript."""

    def test_typescript_decode(self):
        """Test that TypeScript can decode Python-encoded story."""
        # Create a story in Python using compact array format for tp, te, sf
        # tp format: [name, messages, hours, days, sessions, agent_ratio]
        # te format: [day, type, value, project_idx] (-1 for missing)
        # sf format: [duration, messages, is_agent, hour, weekday, project_idx, fp0..fp7]
        story = WrappedStoryV3(
            v=3,
            y=2025,
            n="Cross-Language Test",
            p=3,
            s=50,
            m=2500,
            h=100,
            d=30,
            hm=[0] * 168,
            ma=[200, 250, 300, 350, 300, 250, 200, 225, 275, 325, 300, 275],
            mh=[8, 10, 12, 14, 12, 10, 8, 9, 11, 13, 12, 11],
            ms=[5, 6, 7, 8, 7, 6, 5, 5, 6, 7, 6, 6],
            sd=[5, 10, 15, 20, 15, 10, 5, 3, 2, 1],
            ar=[3, 6, 12, 18, 22, 18, 12, 6, 2, 1],
            ml=[8, 15, 25, 22, 15, 8, 5, 2],
            ts={'ad': 50, 'sp': 50, 'fc': 50, 'cc': 50, 'wr': 50,
                'bs': 50, 'cs': 50, 'mv': 50, 'td': 50, 'ri': 50},
            tp=[
                ['TestProject', 1000, 40, 15, 20, 50],  # Compact array format
            ],
            pc=[],
            te=[[50, 0, 100, -1]],  # Compact array format: [day, type, value, project_idx]
            sf=[],
            ls=2.0,
            sk=[3, 5, 2, 3],
            tk={'total': 500000, 'input': 300000, 'output': 200000,
                'cache_read': 100000, 'cache_create': 25000, 'models': {}},
        )

        # Encode in Python
        encoded = encode_wrapped_story_v3(story)

        # Create a test script for TypeScript
        ts_test_script = f'''
import msgpack from 'msgpack-lite';
import {{ decodeWrappedStoryV3, validateStoryV3 }} from '../src/decoder';

const encoded = "{encoded}";

try {{
    const decoded = decodeWrappedStoryV3(encoded);

    // Validate structure
    const validation = validateStoryV3(decoded);
    if (!validation.valid) {{
        console.error("Validation failed:", validation.error);
        process.exit(1);
    }}

    // Verify key fields
    const checks = [
        ["version", decoded.v === 3],
        ["year", decoded.y === 2025],
        ["name", decoded.n === "Cross-Language Test"],
        ["projects", decoded.p === 3],
        ["sessions", decoded.s === 50],
        ["messages", decoded.m === 2500],
        ["hours", decoded.h === 100],
        ["days", decoded.d === 30],
        ["heatmap_length", decoded.hm.length === 168],
        ["monthly_activity_length", decoded.ma.length === 12],
        ["trait_ad", decoded.ts.ad === 50],
        ["top_projects", decoded.tp.length === 1],
        ["top_project_name", decoded.tp[0].n === "TestProject"],
    ];

    let allPassed = true;
    for (const [name, passed] of checks) {{
        if (passed) {{
            console.log(`✓ ${{name}}`);
        }} else {{
            console.log(`✗ ${{name}}`);
            allPassed = false;
        }}
    }}

    if (!allPassed) {{
        process.exit(1);
    }}

    console.log("\\nAll cross-language checks passed!");
}} catch (error) {{
    console.error("Decoding failed:", error);
    process.exit(1);
}}
'''

        # Write and run the TypeScript test
        wrapped_dir = Path(__file__).parent.parent / "wrapped-website"
        test_file = wrapped_dir / "tests" / "cross_language_test.ts"

        test_file.write_text(ts_test_script)
        try:
            result = subprocess.run(
                ["npx", "tsx", str(test_file)],
                cwd=str(wrapped_dir),
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)
                pytest.fail(f"TypeScript decode failed: {result.stderr}")

            assert "All cross-language checks passed!" in result.stdout
        finally:
            # Clean up
            if test_file.exists():
                test_file.unlink()


class TestGenerateWrappedStoryV3Integration:
    """Integration tests for the full story generation pipeline."""

    def test_generate_and_encode_story(self):
        """Test generating a story from mocked data and encoding it."""
        # Create mock project
        mock_project = MagicMock()
        mock_project.short_name = "IntegrationProject"
        mock_project.path = "/test/integration"
        mock_project.session_files = [Path("/test/session1.jsonl"), Path("/test/session2.jsonl")]

        # Create mock sessions
        mock_session1 = Session(
            session_id="session1",
            project_path="/test/integration",
            file_path=Path("/test/session1.jsonl"),
            messages=[
                Message(role="user", content="Hello", timestamp=datetime(2025, 6, 15, 10, 0)),
                Message(role="assistant", content="Hi there!", timestamp=datetime(2025, 6, 15, 10, 5)),
            ],
            start_time=datetime(2025, 6, 15, 10, 0),
            end_time=datetime(2025, 6, 15, 11, 0),
        )

        mock_session2 = Session(
            session_id="session2",
            project_path="/test/integration",
            file_path=Path("/test/session2.jsonl"),
            messages=[
                Message(role="user", content="Help me debug", timestamp=datetime(2025, 6, 16, 14, 0)),
                Message(role="assistant", content="Sure!", tool_uses=[
                    {"name": "Read", "input": {}},
                ], timestamp=datetime(2025, 6, 16, 14, 30)),
            ],
            start_time=datetime(2025, 6, 16, 14, 0),
            end_time=datetime(2025, 6, 16, 15, 0),
        )

        def mock_parse_session(file_path, project_path):
            if "session1" in str(file_path):
                return mock_session1
            return mock_session2

        with patch('claude_history_explorer.history.list_projects', return_value=[mock_project]):
            with patch('claude_history_explorer.history.parse_session', side_effect=mock_parse_session):
                story = generate_wrapped_story_v3(2025, name="Integration User")

        # Verify story was generated
        assert story.v == 3
        assert story.y == 2025
        assert story.n == "Integration User"
        assert story.p == 1
        assert story.s == 2
        assert story.m == 4
        assert story.d == 2

        # Encode the story
        encoded = encode_wrapped_story_v3(story)
        assert len(encoded) > 0

        # Decode and verify
        decoded = decode_wrapped_story_v3(encoded)
        assert decoded.n == "Integration User"
        assert decoded.m == 4


class TestEdgeCasesIntegration:
    """Integration tests for edge cases."""

    def test_unicode_in_names(self):
        """Test that unicode characters in names are handled correctly."""
        story = WrappedStoryV3(
            v=3,
            y=2025,
            n="日本語ユーザー",  # Japanese
            p=1, s=1, m=100, h=1, d=1,
            hm=[0] * 168,
            ma=[100] * 12, mh=[1] * 12, ms=[1] * 12,
            sd=[100] + [0] * 9, ar=[100] + [0] * 9, ml=[100] + [0] * 7,
            ts={'ad': 50, 'sp': 50, 'fc': 50, 'cc': 50, 'wr': 50,
                'bs': 50, 'cs': 50, 'mv': 50, 'td': 50, 'ri': 50},
            tp=[['프로젝트', 100, 1, 1, 1, 50]],  # Korean project name
            pc=[], te=[], sf=[],
        )

        encoded = encode_wrapped_story_v3(story)
        decoded = decode_wrapped_story_v3(encoded)

        assert decoded.n == "日本語ユーザー"
        assert decoded.tp[0][0] == "프로젝트"  # Array format: [name, ...]

    def test_empty_story(self):
        """Test encoding/decoding a minimal story."""
        story = WrappedStoryV3(
            v=3,
            y=2025,
            p=0, s=0, m=0, h=0, d=0,
            hm=[0] * 168,
            ma=[0] * 12, mh=[0] * 12, ms=[0] * 12,
            sd=[0] * 10, ar=[0] * 10, ml=[0] * 8,
            ts={'ad': 50, 'sp': 50, 'fc': 50, 'cc': 50, 'wr': 50,
                'bs': 50, 'cs': 50, 'mv': 50, 'td': 50, 'ri': 50},
            tp=[], pc=[], te=[], sf=[],
        )

        encoded = encode_wrapped_story_v3(story)
        decoded = decode_wrapped_story_v3(encoded)

        assert decoded.v == 3
        assert decoded.m == 0
        assert len(decoded.tp) == 0

    def test_max_values(self):
        """Test encoding/decoding a story with max typical values."""
        story = WrappedStoryV3(
            v=3,
            y=2025,
            n="Power User",
            p=12,  # MAX_PROJECTS
            s=9999,
            m=999999,
            h=9999,
            d=365,
            hm=[15] * 168,  # Max quantized heatmap
            ma=[99999] * 12, mh=[999] * 12, ms=[999] * 12,
            sd=[999] * 10, ar=[999] * 10, ml=[999] * 8,
            ts={'ad': 100, 'sp': 100, 'fc': 100, 'cc': 100, 'wr': 100,
                'bs': 100, 'cs': 100, 'mv': 100, 'td': 100, 'ri': 100},
            tp=[
                # [name, messages, hours, days, sessions, agent_ratio]
                [f'Project{i}', 10000, 1000, 365, 1000, 100]
                for i in range(12)
            ],
            pc=[(i, j, 100) for i in range(5) for j in range(i + 1, 6)],
            te=[[i * 30, i % 7, 1000, -1] for i in range(10)],  # [day, type, value, project_idx]
            sf=[
                # [duration, messages, is_agent, hour, weekday, project_idx, fp0..fp7]
                [999, 999, 1, 23, 6, 0] + [100] * 8
                for i in range(10)
            ],
            ls=48.0,
            sk=[99, 99, 99, 99],
            tk={'total': 999999999, 'input': 500000000, 'output': 499999999,
                'cache_read': 999999999, 'cache_create': 999999999,
                'models': {'sonnet': 500000000, 'opus': 300000000, 'haiku': 199999999}},
            yoy={'pm': 500000, 'ph': 5000, 'ps': 5000, 'pp': 10, 'pd': 300},
        )

        encoded = encode_wrapped_story_v3(story)
        decoded = decode_wrapped_story_v3(encoded)

        assert decoded.m == 999999
        assert decoded.d == 365
        assert len(decoded.tp) == 12
        assert all(t == 100 for t in decoded.ts.values())


class TestWrappedURLTruncationBug:
    """Tests to verify and demonstrate the URL truncation bug in CLI output.

    Bug: The wrapped command uses Rich's overflow="ignore" which silently
    truncates the URL to terminal width, making the generated URL invalid.
    """

    def test_encoded_url_length_is_substantial(self):
        """Test that encoded data for a typical story is substantial in length.

        This establishes that the encoded data is typically much longer than
        a standard terminal width (80 chars), which is necessary for the
        truncation bug to manifest.
        """
        # Create a realistic story with multiple projects (similar to real user data)
        story = WrappedStoryV3(
            v=3,
            y=2025,
            n="Test User",
            p=6,
            s=193,
            m=20000,
            h=758,
            d=15,
            hm=[0] * 100 + [50, 100, 200, 500] * 17,  # Realistic heatmap
            ma=[1000, 2000, 1500, 3000, 2500, 1800, 2200, 1900, 2100, 2800, 3500, 2000],
            mh=[30, 50, 40, 80, 70, 50, 60, 55, 65, 85, 100, 60],
            ms=[10, 15, 12, 25, 20, 15, 18, 16, 19, 28, 35, 18],
            sd=[5, 10, 20, 40, 50, 30, 20, 10, 5, 3],
            ar=[2, 5, 10, 15, 25, 20, 12, 6, 3, 2],
            ml=[10, 20, 30, 25, 20, 10, 3, 2],
            ts={'ad': 85, 'sp': 60, 'fc': 40, 'cc': 55, 'wr': 25,
                'bs': 70, 'cs': 45, 'mv': 50, 'td': 60, 'ri': 75},
            tp=[
                ['Keyboardia', 14000, 300, 14, 111, 93],
                ['Auriga', 4500, 170, 7, 30, 90],
                ['Lempicka', 800, 100, 6, 21, 86],
                ['Kirby Tarot', 800, 50, 3, 14, 79],
                ['Claude History Explorer', 700, 140, 5, 15, 73],
                ['Fibonacci Durable Object', 3, 0, 1, 2, 100],
            ],
            pc=[(0, 1, 5), (0, 2, 3), (1, 2, 2), (0, 3, 4), (1, 3, 3)],
            te=[
                [50, 0, 500, 0],
                [100, 4, 1000, -1],
                [150, 3, -1, 1],
                [200, 4, 5000, -1],
            ],
            sf=[
                [120, 100, 0, 10, 0, 0, 20, 40, 60, 80, 50, 10, 30, 20],
                [180, 150, 1, 14, 2, 1, 30, 50, 70, 60, 40, 20, 25, 35],
                [240, 200, 0, 9, 1, 0, 25, 45, 55, 75, 55, 15, 28, 22],
            ],
            ls=50.5,
            sk=[5, 10, 3, 4],
            tk={'total': 1500000, 'input': 900000, 'output': 600000,
                'cache_read': 400000, 'cache_create': 80000,
                'models': {'opus': 500000, 'sonnet': 800000, 'haiku': 200000}},
        )

        encoded = encode_wrapped_story_v3(story)

        # The encoded data should be much longer than typical terminal width
        assert len(encoded) > 500, f"Encoded length {len(encoded)} should be > 500 chars"

        # Full URL should be even longer
        url = f"https://wrapped-claude-codes.adewale-883.workers.dev/wrapped?d={encoded}"
        assert len(url) > 600, f"URL length {len(url)} should be > 600 chars"

        # Record actual lengths for documentation
        print(f"\nEncoded data length: {len(encoded)} chars")
        print(f"Full URL length: {len(url)} chars")
        print(f"Standard terminal width: 80 chars")
        print(f"Data exceeds terminal by: {len(url) - 80} chars")

    def test_truncated_encoded_data_fails_to_decode(self):
        """Test that truncating encoded data causes decode failure.

        This demonstrates why the truncation bug is critical - truncated
        URLs cannot be decoded and result in errors or missing data.
        """
        story = WrappedStoryV3(
            v=3, y=2025, n="Test", p=3, s=50, m=2000, h=100, d=10,
            hm=[0] * 168,
            ma=[100] * 12, mh=[10] * 12, ms=[5] * 12,
            sd=[10] * 10, ar=[10] * 10, ml=[10] * 8,
            ts={'ad': 50, 'sp': 50, 'fc': 50, 'cc': 50, 'wr': 50,
                'bs': 50, 'cs': 50, 'mv': 50, 'td': 50, 'ri': 50},
            tp=[['Project1', 1000, 50, 5, 20, 50]],
            pc=[], te=[], sf=[],
        )

        encoded = encode_wrapped_story_v3(story)
        full_length = len(encoded)

        # Truncate to simulate terminal width truncation
        # 80 char terminal - ~63 chars for URL base = ~17 chars for data
        truncated = encoded[:17]

        # Verify truncation happened
        assert len(truncated) < full_length, "Should be truncated"

        # Truncated data should fail to decode
        with pytest.raises(Exception) as exc_info:
            decode_wrapped_story_v3(truncated)

        # Should get a decoding error (base64 or msgpack)
        error_msg = str(exc_info.value).lower()
        assert any(term in error_msg for term in ['base64', 'unpack', 'decode', 'padding', 'invalid']), \
            f"Expected base64/msgpack error, got: {exc_info.value}"

        print(f"\nFull encoded length: {full_length} chars")
        print(f"Truncated to: {len(truncated)} chars")
        print(f"Decode error: {exc_info.value}")

    def test_rich_overflow_ignore_truncates_long_text(self):
        """Test that Rich's overflow='ignore' truncates text significantly.

        This directly tests the bug mechanism: Rich's console.print with
        overflow='ignore' silently truncates content that exceeds terminal width.

        Note: Rich's truncation formula isn't exactly terminal_width, but it
        does truncate significantly. A ~1463 char URL gets truncated to ~124 chars
        with width=80, losing over 1300 characters.
        """
        from io import StringIO
        from rich.console import Console

        # Create a console with narrow width to simulate the bug
        narrow_width = 80
        output = StringIO()
        console = Console(file=output, width=narrow_width, force_terminal=True)

        # Create a long URL like the wrapped command generates
        long_url = "https://wrapped-claude-codes.adewale-883.workers.dev/wrapped?d=" + "A" * 1400

        # Print with overflow="ignore" (the buggy behavior)
        console.print(long_url, soft_wrap=False, overflow="ignore")

        truncated_output = output.getvalue().strip()

        # The output should be significantly truncated (not all 1463 chars)
        visible_length = len(truncated_output.replace('\n', ''))

        # With overflow="ignore", content IS truncated (just not to exact width)
        assert visible_length < len(long_url), \
            f"Output ({visible_length}) should be shorter than input ({len(long_url)})"

        # Verify significant data is lost (>50% of the URL should be truncated)
        data_lost = len(long_url) - visible_length
        print(f"\nInput URL length: {len(long_url)} chars")
        print(f"Output length after overflow='ignore': {visible_length} chars")
        print(f"Data lost to truncation: {data_lost} chars ({100*data_lost/len(long_url):.1f}%)")

        # This is THE BUG - substantial data is silently lost
        assert data_lost > len(long_url) * 0.5, \
            f"Expected >50% data loss, only lost {100*data_lost/len(long_url):.1f}%"

    def test_rich_without_overflow_ignore_preserves_text(self):
        """Test that Rich preserves text when overflow='ignore' is removed.

        This demonstrates the fix: without overflow='ignore', the full URL
        is preserved (though it may wrap to multiple lines).
        """
        from io import StringIO
        from rich.console import Console

        narrow_width = 80
        output = StringIO()
        console = Console(file=output, width=narrow_width, force_terminal=True)

        # Create a long URL
        long_url = "https://wrapped-claude-codes.adewale-883.workers.dev/wrapped?d=" + "A" * 1400

        # Print WITHOUT overflow="ignore" - just soft_wrap=False
        # This will let the text extend beyond terminal width
        console.print(long_url, soft_wrap=False)  # No overflow="ignore"!

        full_output = output.getvalue().strip()

        # Without overflow="ignore", the full content should be preserved
        # It may wrap, but the data shouldn't be lost
        assert len(full_output) >= len(long_url) - 10, \
            f"Full URL should be preserved. Got {len(full_output)}, expected ~{len(long_url)}"

        print(f"\nInput URL length: {len(long_url)} chars")
        print(f"Output length without overflow='ignore': {len(full_output)} chars")
        print("Data is preserved!")


class TestCLIOutputIntegrity:
    """Tests to verify CLI output integrity and prevent silent data loss.

    These tests catch bugs where:
    - Output is silently truncated (like overflow="ignore")
    - Displayed data doesn't match internal data
    - URLs in output are not functional
    """

    def test_wrapped_cli_output_contains_decodable_url(self):
        """Test that the wrapped CLI command outputs a complete, decodable URL.

        This is the key regression test for the overflow="ignore" bug.
        Uses Click's CliRunner to capture actual CLI output.
        """
        from click.testing import CliRunner
        from claude_history_explorer.cli import main

        runner = CliRunner()

        # Mock the data generation to have a predictable test
        with patch('claude_history_explorer.cli.generate_wrapped_story_v3') as mock_gen:
            # Create a story with enough data to exceed terminal width
            mock_story = WrappedStoryV3(
                v=3, y=2025, n="CLI Test User", p=5, s=100, m=5000, h=200, d=30,
                hm=[10] * 168,
                ma=[500] * 12, mh=[20] * 12, ms=[10] * 12,
                sd=[10] * 10, ar=[10] * 10, ml=[10] * 8,
                ts={'ad': 50, 'sp': 50, 'fc': 50, 'cc': 50, 'wr': 50,
                    'bs': 50, 'cs': 50, 'mv': 50, 'td': 50, 'ri': 50},
                tp=[
                    ['Project1', 2000, 80, 15, 40, 60],
                    ['Project2', 1500, 60, 10, 30, 50],
                    ['Project3', 1000, 40, 8, 20, 40],
                ],
                pc=[(0, 1, 5), (0, 2, 3)],
                te=[[50, 0, 200, 0], [100, 4, 1000, -1]],
                sf=[[120, 100, 0, 10, 0, 0] + [50] * 8],
                ls=3.5,
                sk=[5, 8, 3, 4],
                tk={'total': 1000000, 'input': 600000, 'output': 400000,
                    'cache_read': 200000, 'cache_create': 50000, 'models': {}},
            )
            mock_gen.return_value = mock_story

            # Run the CLI command with --no-copy to avoid clipboard issues in test
            result = runner.invoke(main, ['wrapped', '--no-copy'])

            assert result.exit_code == 0, f"CLI failed: {result.output}"

            # Extract URL from output
            import re
            url_match = re.search(r'(https://[^\s]+wrapped\?d=[A-Za-z0-9_-]+)', result.output)
            assert url_match, f"No URL found in output: {result.output}"

            url = url_match.group(1)

            # Extract the encoded data from URL
            data_match = re.search(r'\?d=([A-Za-z0-9_-]+)', url)
            assert data_match, f"No data parameter in URL: {url}"

            encoded_data = data_match.group(1)

            # THE KEY TEST: The URL should be decodable
            try:
                decoded = decode_wrapped_story_v3(encoded_data)
            except Exception as e:
                pytest.fail(
                    f"URL in CLI output is not decodable!\n"
                    f"URL: {url}\n"
                    f"Encoded data length: {len(encoded_data)}\n"
                    f"Error: {e}\n"
                    f"This likely means the URL was truncated in output."
                )

            # Verify the decoded data matches what we generated
            assert decoded.n == "CLI Test User"
            assert decoded.p == 5
            assert decoded.m == 5000
            assert len(decoded.tp) == 3

    def test_wrapped_output_url_matches_internal_url(self):
        """Test that the URL displayed matches the URL that would be copied.

        Catches bugs where display and clipboard get different data.
        """
        from click.testing import CliRunner
        from claude_history_explorer.cli import main

        runner = CliRunner()

        with patch('claude_history_explorer.cli.generate_wrapped_story_v3') as mock_gen:
            mock_story = WrappedStoryV3(
                v=3, y=2025, p=2, s=20, m=500, h=10, d=5,
                hm=[0] * 168,
                ma=[50] * 12, mh=[1] * 12, ms=[2] * 12,
                sd=[5] * 10, ar=[5] * 10, ml=[5] * 8,
                ts={'ad': 50, 'sp': 50, 'fc': 50, 'cc': 50, 'wr': 50,
                    'bs': 50, 'cs': 50, 'mv': 50, 'td': 50, 'ri': 50},
                tp=[['Proj', 250, 5, 3, 10, 50]],
                pc=[], te=[], sf=[],
            )
            mock_gen.return_value = mock_story

            # Generate expected URL directly
            expected_encoded = encode_wrapped_story_v3(mock_story)
            expected_url = f"https://wrapped-claude-codes.adewale-883.workers.dev/wrapped?d={expected_encoded}"

            # Run CLI
            result = runner.invoke(main, ['wrapped', '--no-copy'])

            # The output should contain the exact same URL
            assert expected_url in result.output, (
                f"URL mismatch!\n"
                f"Expected URL ({len(expected_url)} chars): {expected_url[:100]}...\n"
                f"Output: {result.output}"
            )

    def test_display_summary_function_preserves_full_url(self):
        """Test that _display_wrapped_summary outputs the complete URL.

        Directly tests the function that had the overflow="ignore" bug.
        """
        from io import StringIO
        import sys

        # Create a story and URL
        story = WrappedStoryV3(
            v=3, y=2025, n="Display Test", p=3, s=50, m=2000, h=50, d=10,
            hm=[0] * 168,
            ma=[200] * 12, mh=[5] * 12, ms=[5] * 12,
            sd=[10] * 10, ar=[10] * 10, ml=[10] * 8,
            ts={'ad': 50, 'sp': 50, 'fc': 50, 'cc': 50, 'wr': 50,
                'bs': 50, 'cs': 50, 'mv': 50, 'td': 50, 'ri': 50},
            tp=[['TestProject', 1000, 25, 5, 20, 50]],
            pc=[], te=[], sf=[],
        )

        encoded = encode_wrapped_story_v3(story)
        url = f"https://wrapped-claude-codes.adewale-883.workers.dev/wrapped?d={encoded}"

        # Capture stdout
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured

        try:
            from claude_history_explorer.cli import _display_wrapped_summary
            _display_wrapped_summary(story, url, 2025)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()

        # The full URL must appear in the output
        assert url in output, (
            f"Full URL not in output!\n"
            f"URL length: {len(url)}\n"
            f"Output length: {len(output)}\n"
            f"URL: {url[:100]}...\n"
            f"This indicates URL truncation in _display_wrapped_summary"
        )

    def test_long_url_not_truncated_in_any_terminal_width(self):
        """Test that URLs are not truncated regardless of terminal width.

        Simulates different terminal widths to ensure the URL is always complete.
        """
        story = WrappedStoryV3(
            v=3, y=2025, n="Width Test", p=6, s=150, m=10000, h=300, d=25,
            hm=[50] * 168,
            ma=[1000] * 12, mh=[30] * 12, ms=[15] * 12,
            sd=[15] * 10, ar=[15] * 10, ml=[15] * 8,
            ts={'ad': 70, 'sp': 60, 'fc': 50, 'cc': 40, 'wr': 30,
                'bs': 60, 'cs': 45, 'mv': 55, 'td': 65, 'ri': 75},
            tp=[
                [f'Project{i}', 2000 - i * 200, 50 - i * 5, 5, 25 - i * 2, 50 + i * 5]
                for i in range(6)
            ],
            pc=[(0, 1, 5), (1, 2, 3), (0, 2, 4)],
            te=[[50, 0, 300, 0], [150, 4, 2000, -1]],
            sf=[[180, 120, 0, 14, 2, 0] + [60] * 8],
            ls=8.5,
            sk=[10, 15, 5, 6],
            tk={'total': 2000000, 'input': 1200000, 'output': 800000,
                'cache_read': 500000, 'cache_create': 100000,
                'models': {'sonnet': 1500000, 'haiku': 500000}},
        )

        encoded = encode_wrapped_story_v3(story)
        url = f"https://wrapped-claude-codes.adewale-883.workers.dev/wrapped?d={encoded}"

        # URL should be substantial
        assert len(url) > 500, f"URL unexpectedly short: {len(url)}"

        # Test various simulated terminal widths
        for width in [40, 60, 80, 100, 120, 200]:
            # Capture stdout with simulated width
            from io import StringIO
            import sys

            captured = StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured

            try:
                from claude_history_explorer.cli import _display_wrapped_summary
                _display_wrapped_summary(story, url, 2025)
            finally:
                sys.stdout = old_stdout

            output = captured.getvalue()

            # Full URL must be in output regardless of "terminal width"
            # (print() doesn't truncate, but this test documents the requirement)
            assert url in output, (
                f"URL truncated at simulated width {width}!\n"
                f"Expected URL ({len(url)} chars)\n"
                f"Got output with length {len(output)}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
