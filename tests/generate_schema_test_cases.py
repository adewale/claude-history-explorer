#!/usr/bin/env python3
"""Generate test cases for Python/TypeScript schema alignment.

This script generates JSON test cases that can be consumed by both Python tests
and TypeScript tests to verify the schema alignment between encoder and decoder.

Usage:
    python tests/generate_schema_test_cases.py
"""

import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_history_explorer.history import (
    WrappedStoryV3,
    encode_wrapped_story_v3,
    quantize_heatmap,
    HEATMAP_QUANT_SCALE,
)


def story_to_expected_json(story: WrappedStoryV3) -> dict:
    """Convert a WrappedStoryV3 to the expected decoded JSON format.

    This matches what the TypeScript decoder should produce.
    Key transformations:
    - Heatmap is quantized to 0-15 scale (same as encoder does)
    - tp, te, sf are decoded from arrays to objects
    - Empty ts/sk/tk get defaults applied by decoder
    """
    # Quantize heatmap the same way the encoder does
    quantized_hm = quantize_heatmap(story.hm) if story.hm else []

    # Defaults applied by TypeScript decoder for empty values
    default_ts = {
        "ad": 50, "sp": 50, "fc": 50, "cc": 50, "wr": 50,
        "bs": 50, "cs": 50, "mv": 50, "td": 50, "ri": 50
    }
    default_sk = [0, 0, 0, 0]
    default_tk = {
        "total": 0, "input": 0, "output": 0,
        "cache_read": 0, "cache_create": 0, "models": {}
    }

    result = {
        "v": 3,  # TypeScript always sets v to 3
        "y": story.y,
        "p": story.p,
        "s": story.s,
        "m": story.m,
        "h": story.h,
        "d": story.d,
        "hm": quantized_hm,  # Quantized (RLE is decoded by TypeScript)
        "ma": story.ma if story.ma else [],
        "mh": story.mh if story.mh else [],
        "ms": story.ms if story.ms else [],
        "sd": story.sd if story.sd else [],
        "ar": story.ar if story.ar else [],
        "ml": story.ml if story.ml else [],
        # Use defaults if ts is empty
        "ts": story.ts if story.ts else default_ts,
        # tp: decode [name, msgs, hours, days, sessions, ratio] to object
        "tp": [
            {"n": proj[0] or "", "m": proj[1] or 0, "h": proj[2] or 0,
             "d": proj[3] or 0, "s": proj[4] or 0, "ar": proj[5] or 0}
            for proj in story.tp
        ],
        "pc": [list(tup) for tup in story.pc],  # Tuples to arrays
        # te: decode [day, type, value, project_idx] to object
        # -1 values are omitted
        "te": [
            _decode_event(ev) for ev in story.te
        ],
        # sf: decode 14-element array to object
        "sf": [
            _decode_fingerprint(fp) for fp in story.sf
        ],
        "ls": round(story.ls, 1),
        # Use defaults if sk is empty
        "sk": story.sk if story.sk else default_sk,
        # Use defaults if tk is empty
        "tk": story.tk if story.tk else default_tk,
    }

    if story.n:
        result["n"] = story.n
    if story.yoy:
        result["yoy"] = story.yoy

    return result


def _decode_event(arr: list) -> dict:
    """Decode timeline event array to object format."""
    event = {"d": arr[0] or 0, "t": arr[1] or 0}
    if len(arr) > 2 and arr[2] != -1:
        event["v"] = arr[2]
    if len(arr) > 3 and arr[3] != -1:
        event["p"] = arr[3]
    return event


def _decode_fingerprint(arr: list) -> dict:
    """Decode fingerprint array to object format."""
    return {
        "d": arr[0] or 0,
        "m": arr[1] or 0,
        "a": arr[2] == 1,
        "h": arr[3] or 0,
        "w": arr[4] or 0,
        "pi": arr[5] or 0,
        "fp": list(arr[6:14]) if len(arr) >= 14 else [0] * 8,
    }


def generate_test_cases() -> list[dict]:
    """Generate comprehensive test cases for schema alignment."""
    cases = []

    # =========================================================================
    # Test Case 1: Minimal valid data
    # =========================================================================
    minimal = WrappedStoryV3(
        y=2025,
        p=1,
        s=1,
        m=10,
        h=1,
        d=1,
        hm=[0] * 168,  # Empty heatmap
        ma=[0] * 12,
        mh=[0] * 12,
        ms=[0] * 12,
        sd=[],
        ar=[],
        ml=[],
        ts={"ad": 50, "sp": 50, "fc": 50, "cc": 50, "wr": 50,
            "bs": 50, "cs": 50, "mv": 50, "td": 50, "ri": 50},
        tp=[["Test", 10, 1, 1, 1, 50]],  # name, msgs, hours, days, sessions, ratio
        pc=[],
        te=[],
        sf=[],
        ls=0.5,
        sk=[0, 0, 0, 0],
        tk={"total": 100, "input": 50, "output": 50,
            "cache_read": 0, "cache_create": 0, "models": {}},
    )
    cases.append({
        "id": "minimal",
        "description": "Minimal valid payload with one project",
        "encoded": encode_wrapped_story_v3(minimal),
        "expected": story_to_expected_json(minimal),
    })

    # =========================================================================
    # Test Case 2: Full data with all fields populated
    # =========================================================================
    full = WrappedStoryV3(
        y=2025,
        n="Test User",
        p=5,
        s=100,
        m=5000,
        h=250,
        d=45,
        hm=[i % 15 for i in range(168)],  # Pattern heatmap
        ma=[100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200],
        mh=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120],
        ms=[5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60],
        sd=[10, 20, 30, 25, 15, 5, 3, 2, 1, 0],  # 10 buckets
        ar=[5, 10, 15, 20, 25, 25, 20, 15, 10, 5],  # 10 buckets
        ml=[100, 200, 300, 400, 300, 200, 100, 50],  # 8 buckets
        ts={"ad": 80, "sp": 30, "fc": 60, "cc": 70, "wr": 20,
            "bs": 45, "cs": 55, "mv": 65, "td": 75, "ri": 85},
        tp=[
            ["Project Alpha", 2000, 100, 30, 40, 70],
            ["Project Beta", 1500, 80, 25, 30, 50],
            ["Project Gamma", 1000, 50, 15, 20, 30],
        ],
        pc=[(0, 1, 10), (0, 2, 5), (1, 2, 3)],
        te=[
            [15, 0, 500, 0],   # peak_day event
            [45, 1, 8, 1],     # marathon event
            [90, 2, 100, 0],   # milestone event
            [120, 3, -1, 2],   # tool_mastery (no value)
            [180, 4, -1, -1],  # breakthrough (no value, no project)
        ],
        sf=[
            [120, 50, 1, 14, 2, 0, 80, 60, 70, 50, 40, 30, 20, 10],  # 14 elements
            [60, 25, 0, 10, 5, 1, 90, 70, 60, 50, 40, 30, 20, 10],
        ],
        ls=8.5,
        sk=[5, 7, 3, 4],  # count, longest, current, avg
        tk={
            "total": 1000000,
            "input": 600000,
            "output": 400000,
            "cache_read": 50000,
            "cache_create": 10000,
            "models": {"claude-3-opus": 500000, "claude-3-sonnet": 500000}
        },
        yoy={"pm": 3000, "ph": 150, "ps": 60, "pp": 3, "pd": 30},
    )
    cases.append({
        "id": "full",
        "description": "Full data with all fields populated",
        "encoded": encode_wrapped_story_v3(full),
        "expected": story_to_expected_json(full),
    })

    # =========================================================================
    # Test Case 3: Unicode project names
    # =========================================================================
    unicode_story = WrappedStoryV3(
        y=2025,
        p=3,
        s=10,
        m=100,
        h=10,
        d=5,
        hm=[0] * 168,
        ma=[10] * 12,
        mh=[1] * 12,
        ms=[1] * 12,
        sd=[],
        ar=[],
        ml=[],
        ts={"ad": 50, "sp": 50, "fc": 50, "cc": 50, "wr": 50,
            "bs": 50, "cs": 50, "mv": 50, "td": 50, "ri": 50},
        tp=[
            ["Emoji Project", 30, 3, 2, 3, 40],
            ["Cafe Project", 35, 4, 2, 4, 50],
            ["Nihongo Project", 35, 3, 1, 3, 60],
        ],
        pc=[],
        te=[],
        sf=[],
        ls=2.0,
        sk=[0, 0, 0, 0],
        tk={"total": 0, "input": 0, "output": 0,
            "cache_read": 0, "cache_create": 0, "models": {}},
    )
    cases.append({
        "id": "unicode",
        "description": "Project names with non-ASCII characters",
        "encoded": encode_wrapped_story_v3(unicode_story),
        "expected": story_to_expected_json(unicode_story),
    })

    # =========================================================================
    # Test Case 4: Edge values (zeros and maximums)
    # =========================================================================
    edge = WrappedStoryV3(
        y=2025,
        p=0,
        s=0,
        m=0,
        h=0,
        d=0,
        hm=[0] * 168,
        ma=[0] * 12,
        mh=[0] * 12,
        ms=[0] * 12,
        sd=[],
        ar=[],
        ml=[],
        ts={"ad": 0, "sp": 100, "fc": 0, "cc": 100, "wr": 0,
            "bs": 100, "cs": 0, "mv": 100, "td": 0, "ri": 100},
        tp=[],
        pc=[],
        te=[],
        sf=[],
        ls=0.0,
        sk=[0, 0, 0, 0],
        tk={"total": 0, "input": 0, "output": 0,
            "cache_read": 0, "cache_create": 0, "models": {}},
    )
    cases.append({
        "id": "edge_zeros",
        "description": "All zero/empty values and extreme trait scores",
        "encoded": encode_wrapped_story_v3(edge),
        "expected": story_to_expected_json(edge),
    })

    # =========================================================================
    # Test Case 5: Empty optional arrays (tp, te, sf, pc can be empty)
    # Note: ts, sk, tk need values because empty {} and [] are truthy in JS,
    # so the decoder won't apply defaults for them.
    # =========================================================================
    empty_optional = WrappedStoryV3(
        y=2025,
        p=1,
        s=5,
        m=50,
        h=5,
        d=3,
        hm=[],  # Empty heatmap (allowed)
        ma=[],
        mh=[],
        ms=[],
        sd=[],
        ar=[],
        ml=[],
        ts={"ad": 50, "sp": 50, "fc": 50, "cc": 50, "wr": 50,
            "bs": 50, "cs": 50, "mv": 50, "td": 50, "ri": 50},
        tp=[],  # No projects - valid
        pc=[],  # No co-occurrence - valid
        te=[],  # No events - valid
        sf=[],  # No fingerprints - valid
        ls=1.0,
        sk=[0, 0, 0, 0],  # Must provide 4 elements
        tk={"total": 0, "input": 0, "output": 0,
            "cache_read": 0, "cache_create": 0, "models": {}},
    )
    cases.append({
        "id": "empty_optional_arrays",
        "description": "Empty optional arrays (tp, te, sf, pc)",
        "encoded": encode_wrapped_story_v3(empty_optional),
        "expected": story_to_expected_json(empty_optional),
    })

    # =========================================================================
    # Test Case 6: Maximum projects (12)
    # =========================================================================
    max_projects = WrappedStoryV3(
        y=2025,
        p=12,
        s=120,
        m=12000,
        h=600,
        d=100,
        hm=[10] * 168,
        ma=[1000] * 12,
        mh=[50] * 12,
        ms=[10] * 12,
        sd=[10] * 10,
        ar=[10] * 10,
        ml=[100] * 8,
        ts={"ad": 50, "sp": 50, "fc": 50, "cc": 50, "wr": 50,
            "bs": 50, "cs": 50, "mv": 50, "td": 50, "ri": 50},
        tp=[
            [f"Project {i+1}", 1000, 50, 10, 10, 50]
            for i in range(12)
        ],
        pc=[(i, i+1, 5) for i in range(11)],
        te=[],
        sf=[],
        ls=10.0,
        sk=[10, 14, 5, 7],
        tk={"total": 5000000, "input": 3000000, "output": 2000000,
            "cache_read": 100000, "cache_create": 50000, "models": {}},
    )
    cases.append({
        "id": "max_projects",
        "description": "Maximum 12 projects with co-occurrence",
        "encoded": encode_wrapped_story_v3(max_projects),
        "expected": story_to_expected_json(max_projects),
    })

    # =========================================================================
    # Test Case 7: All timeline event types
    # =========================================================================
    all_events = WrappedStoryV3(
        y=2025,
        p=2,
        s=20,
        m=200,
        h=20,
        d=10,
        hm=[5] * 168,
        ma=[20] * 12,
        mh=[2] * 12,
        ms=[2] * 12,
        sd=[],
        ar=[],
        ml=[],
        ts={"ad": 50, "sp": 50, "fc": 50, "cc": 50, "wr": 50,
            "bs": 50, "cs": 50, "mv": 50, "td": 50, "ri": 50},
        tp=[
            ["Main Project", 150, 15, 8, 15, 60],
            ["Side Project", 50, 5, 2, 5, 40],
        ],
        pc=[(0, 1, 2)],
        te=[
            [10, 0, 50, 0],    # type 0: peak_day
            [20, 1, 12, 0],    # type 1: marathon
            [30, 2, 1000, 0],  # type 2: milestone
            [40, 3, -1, 1],    # type 3: tool_mastery (no value)
            [50, 4, -1, -1],   # type 4: breakthrough (no value, no project)
        ],
        sf=[],
        ls=12.0,
        sk=[3, 5, 2, 3],
        tk={"total": 0, "input": 0, "output": 0,
            "cache_read": 0, "cache_create": 0, "models": {}},
    )
    cases.append({
        "id": "all_event_types",
        "description": "All 5 timeline event types",
        "encoded": encode_wrapped_story_v3(all_events),
        "expected": story_to_expected_json(all_events),
    })

    # =========================================================================
    # Test Case 8: Session fingerprints with various values
    # =========================================================================
    fingerprints = WrappedStoryV3(
        y=2025,
        p=1,
        s=5,
        m=100,
        h=10,
        d=5,
        hm=[0] * 168,
        ma=[10] * 12,
        mh=[1] * 12,
        ms=[1] * 12,
        sd=[],
        ar=[],
        ml=[],
        ts={"ad": 50, "sp": 50, "fc": 50, "cc": 50, "wr": 50,
            "bs": 50, "cs": 50, "mv": 50, "td": 50, "ri": 50},
        tp=[["Test Project", 100, 10, 5, 5, 50]],
        pc=[],
        te=[],
        sf=[
            # [duration, msgs, is_agent, hour, weekday, proj_idx, fp0..fp7]
            [30, 10, 0, 9, 0, 0, 50, 50, 50, 50, 50, 50, 50, 50],   # Not agent
            [60, 20, 1, 14, 2, 0, 80, 70, 60, 50, 40, 30, 20, 10],  # Agent
            [120, 40, 0, 22, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0],         # All zeros fp
            [180, 60, 1, 3, 6, 0, 100, 100, 100, 100, 100, 100, 100, 100],  # All max fp
            [5, 2, 0, 8, 1, 0, 25, 75, 25, 75, 25, 75, 25, 75],     # Short session
        ],
        ls=3.0,
        sk=[0, 0, 0, 0],
        tk={"total": 0, "input": 0, "output": 0,
            "cache_read": 0, "cache_create": 0, "models": {}},
    )
    cases.append({
        "id": "session_fingerprints",
        "description": "Various session fingerprint patterns",
        "encoded": encode_wrapped_story_v3(fingerprints),
        "expected": story_to_expected_json(fingerprints),
    })

    # =========================================================================
    # Test Case 9: Heatmap with RLE compression trigger
    # =========================================================================
    rle_heatmap = WrappedStoryV3(
        y=2025,
        p=1,
        s=50,
        m=500,
        h=50,
        d=20,
        # Pattern that benefits from RLE: many consecutive same values
        hm=[0] * 48 + [10] * 48 + [0] * 48 + [15] * 24,
        ma=[50] * 12,
        mh=[5] * 12,
        ms=[5] * 12,
        sd=[],
        ar=[],
        ml=[],
        ts={"ad": 50, "sp": 50, "fc": 50, "cc": 50, "wr": 50,
            "bs": 50, "cs": 50, "mv": 50, "td": 50, "ri": 50},
        tp=[["RLE Test", 500, 50, 20, 50, 50]],
        pc=[],
        te=[],
        sf=[],
        ls=5.0,
        sk=[2, 3, 0, 2],
        tk={"total": 0, "input": 0, "output": 0,
            "cache_read": 0, "cache_create": 0, "models": {}},
    )
    cases.append({
        "id": "heatmap_rle",
        "description": "Heatmap pattern that triggers RLE compression",
        "encoded": encode_wrapped_story_v3(rle_heatmap),
        "expected": story_to_expected_json(rle_heatmap),
    })

    # =========================================================================
    # Test Case 10: Float precision (ls field)
    # =========================================================================
    float_precision = WrappedStoryV3(
        y=2025,
        p=1,
        s=1,
        m=10,
        h=1,
        d=1,
        hm=[0] * 168,
        ma=[0] * 12,
        mh=[0] * 12,
        ms=[0] * 12,
        sd=[],
        ar=[],
        ml=[],
        ts={"ad": 50, "sp": 50, "fc": 50, "cc": 50, "wr": 50,
            "bs": 50, "cs": 50, "mv": 50, "td": 50, "ri": 50},
        tp=[["Float Test", 10, 1, 1, 1, 50]],
        pc=[],
        te=[],
        sf=[],
        ls=2.7,  # Should be preserved as 2.7 after round(x, 1)
        sk=[0, 0, 0, 0],
        tk={"total": 0, "input": 0, "output": 0,
            "cache_read": 0, "cache_create": 0, "models": {}},
    )
    cases.append({
        "id": "float_precision",
        "description": "Float value precision for ls field",
        "encoded": encode_wrapped_story_v3(float_precision),
        "expected": story_to_expected_json(float_precision),
    })

    return cases


def write_test_cases(output_path: Path) -> None:
    """Generate and write test cases to JSON file."""
    cases = generate_test_cases()

    with open(output_path, 'w') as f:
        json.dump(cases, f, indent=2)

    print(f"Generated {len(cases)} test cases to {output_path}")


def main():
    """Main entry point."""
    output_path = Path(__file__).parent / "fixtures" / "schema_test_cases.json"
    write_test_cases(output_path)


if __name__ == "__main__":
    main()
