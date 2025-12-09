"""Tests for the Wrapped story feature."""

import pytest
from datetime import datetime

from claude_history_explorer.history import (
    WrappedStory,
    encode_wrapped_story,
    decode_wrapped_story,
    filter_sessions_by_year,
    SessionInfo,
)


class TestWrappedStory:
    """Tests for WrappedStory dataclass."""

    def test_wrapped_story_creation(self):
        """Test basic WrappedStory creation."""
        story = WrappedStory(
            y=2025,
            p=5,
            s=100,
            m=10000,
            h=500.0,
            t=["Agent-driven", "Deep-work focused"],
            c="Heavy delegation",
            w="Steady",
            pp="myproject",
            pm=5000,
            ci=3,
            ls=8.5,
            a=[100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200],
            tp=[{"n": "myproject", "m": 5000, "d": 30}],
            n="Alice",
        )
        assert story.y == 2025
        assert story.p == 5
        assert story.m == 10000
        assert story.n == "Alice"

    def test_wrapped_story_to_dict(self):
        """Test WrappedStory serialization to dict."""
        story = WrappedStory(
            y=2025,
            p=3,
            s=50,
            m=5000,
            h=250.5,
            t=["Hands-on"],
            c="Balanced",
            w="Rapid-fire",
            pp="test",
            pm=2000,
        )
        d = story.to_dict()
        assert d["y"] == 2025
        assert d["p"] == 3
        assert d["m"] == 5000
        assert d["h"] == 250.5
        assert "n" not in d  # Name not included when None

    def test_wrapped_story_from_dict(self):
        """Test WrappedStory deserialization from dict."""
        d = {
            "y": 2024,
            "p": 10,
            "s": 200,
            "m": 20000,
            "h": 1000.0,
            "t": ["Collaborative"],
            "c": "Hands-on",
            "w": "Methodical",
            "pp": "bigproject",
            "pm": 10000,
            "ci": 5,
            "ls": 12.0,
            "a": [0] * 12,
            "tp": [],
            "n": "Bob",
        }
        story = WrappedStory.from_dict(d)
        assert story.y == 2024
        assert story.n == "Bob"
        assert story.ci == 5


class TestEncoding:
    """Tests for encoding and decoding."""

    def test_encode_decode_round_trip(self):
        """Test that encoding and decoding preserves data."""
        story = WrappedStory(
            y=2025,
            p=5,
            s=100,
            m=10000,
            h=500.0,
            t=["Agent-driven", "Deep-work focused", "High-intensity"],
            c="Heavy delegation",
            w="Steady",
            pp="myproject",
            pm=5000,
            ci=3,
            ls=8.5,
            a=[100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200],
            tp=[
                {"n": "myproject", "m": 5000, "d": 30},
                {"n": "other", "m": 2000, "d": 15},
            ],
            n="Alice",
        )
        encoded = encode_wrapped_story(story)
        decoded = decode_wrapped_story(encoded)

        assert decoded.y == story.y
        assert decoded.p == story.p
        assert decoded.s == story.s
        assert decoded.m == story.m
        assert decoded.n == story.n
        assert decoded.t == story.t
        assert decoded.tp == story.tp

    def test_encoded_string_is_url_safe(self):
        """Test that encoded string is URL-safe."""
        story = WrappedStory(
            y=2025,
            p=1,
            s=1,
            m=1,
            h=1.0,
            t=[],
            c="",
            w="",
            pp="",
            pm=0,
        )
        encoded = encode_wrapped_story(story)
        # URL-safe base64 uses only alphanumeric, -, and _
        assert all(c.isalnum() or c in "-_" for c in encoded)

    def test_decode_invalid_data(self):
        """Test that decoding invalid data raises ValueError."""
        with pytest.raises(ValueError):
            decode_wrapped_story("not-valid-base64!!!")


class TestFilterSessionsByYear:
    """Tests for year filtering."""

    def test_filter_sessions_by_year(self):
        """Test filtering sessions by year."""
        sessions = [
            SessionInfo(
                session_id="1",
                start_time=datetime(2024, 6, 15),
                end_time=datetime(2024, 6, 15),
                duration_minutes=60,
                message_count=100,
                user_message_count=50,
                is_agent=False,
                slug=None,
            ),
            SessionInfo(
                session_id="2",
                start_time=datetime(2025, 1, 15),
                end_time=datetime(2025, 1, 15),
                duration_minutes=60,
                message_count=200,
                user_message_count=100,
                is_agent=False,
                slug=None,
            ),
            SessionInfo(
                session_id="3",
                start_time=datetime(2025, 12, 31),
                end_time=datetime(2026, 1, 1),  # Spans year boundary
                duration_minutes=120,
                message_count=300,
                user_message_count=150,
                is_agent=False,
                slug=None,
            ),
        ]

        filtered_2024 = filter_sessions_by_year(sessions, 2024)
        filtered_2025 = filter_sessions_by_year(sessions, 2025)

        assert len(filtered_2024) == 1
        assert filtered_2024[0].session_id == "1"

        assert len(filtered_2025) == 2
        assert filtered_2025[0].session_id == "2"
        assert filtered_2025[1].session_id == "3"  # Assigned to start year

    def test_filter_sessions_empty_list(self):
        """Test filtering empty session list."""
        result = filter_sessions_by_year([], 2025)
        assert result == []
