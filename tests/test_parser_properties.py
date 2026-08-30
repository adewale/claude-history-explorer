"""Property tests for the untrusted JSONL session boundary."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import given
from hypothesis import strategies as st

from claude_history_explorer.parser import parse_session

JSON_SCALARS = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(),
)
JSON_NON_OBJECTS = st.recursive(
    JSON_SCALARS,
    lambda children: st.lists(children, max_size=5),
    max_leaves=10,
)
MESSAGE_TEXT = st.text(max_size=200).map(lambda value: f"message:{value}")
JSONL_RECORDS = st.lists(
    st.one_of(
        JSON_NON_OBJECTS.map(lambda value: (value, None)),
        MESSAGE_TEXT.map(
            lambda content: (
                {"type": "user", "message": {"content": content}},
                content.strip(),
            )
        ),
    ),
    max_size=20,
)


@given(JSONL_RECORDS)
def test_session_parser_ignores_non_object_json_values(records):
    """Every JSON value is safe, while object messages retain their content."""
    with TemporaryDirectory() as directory:
        session_file = Path(directory) / "generated.jsonl"
        session_file.write_text(
            "".join(f"{json.dumps(value)}\n" for value, _expected in records),
            encoding="utf-8",
        )

        session = parse_session(session_file)

        assert [message.content for message in session.messages] == [
            expected for _value, expected in records if expected is not None
        ]
