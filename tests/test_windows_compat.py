"""Tests for Windows compatibility.

Covers:
  1. Project discovery: dirs not starting with '-' must be found
  2. Path decoding: Windows drive-letter encoded names (C--Users-...)
  3. Path decoding: fallback uses os.sep not hardcoded '/'
  4. basename/short_name: must work regardless of path separator
  5. CLI display: must use Project.short_name, not raw split('/')
  6. Console encoding: reconfigure guard must be safe
"""

import re
import tempfile
from pathlib import Path
from unittest.mock import patch

from claude_history_explorer.models import Project
from claude_history_explorer.projects import list_projects


# ---------------------------------------------------------------------------
# Issue 1: projects.py filter — startswith("-") excludes Windows dirs
# ---------------------------------------------------------------------------

class TestProjectDiscovery:
    """list_projects must discover both Unix and Windows project dirs."""

    def _make_projects_dir(self, tmp, names):
        projects_dir = Path(tmp) / "projects"
        projects_dir.mkdir()
        for n in names:
            d = projects_dir / n
            d.mkdir()
            (d / "session.jsonl").write_text(
                '{"type":"user","message":{"content":"hi"}}\n'
            )
        return projects_dir

    def test_discovers_unix_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = self._make_projects_dir(tmp, ["-Users-ade-foo"])
            with patch("claude_history_explorer.projects.get_projects_dir",
                       return_value=projects_dir):
                projects = list_projects()
                assert len(projects) == 1

    def test_discovers_windows_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = self._make_projects_dir(tmp, ["C--Users-Moho-project"])
            with patch("claude_history_explorer.projects.get_projects_dir",
                       return_value=projects_dir):
                projects = list_projects()
                assert len(projects) == 1

    def test_discovers_mixed_unix_and_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = self._make_projects_dir(
                tmp, ["-Users-ade-foo", "D--dev-bar"]
            )
            with patch("claude_history_explorer.projects.get_projects_dir",
                       return_value=projects_dir):
                projects = list_projects()
                assert len(projects) == 2

    def test_excludes_hidden_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = self._make_projects_dir(
                tmp, ["-Users-ade-foo", ".hidden"]
            )
            with patch("claude_history_explorer.projects.get_projects_dir",
                       return_value=projects_dir):
                projects = list_projects()
                assert len(projects) == 1

    def test_excludes_plain_non_encoded_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = self._make_projects_dir(
                tmp, ["-Users-ade-foo", "cache", "logs"]
            )
            with patch("claude_history_explorer.projects.get_projects_dir",
                       return_value=projects_dir):
                projects = list_projects()
                assert [project.name for project in projects] == ["-Users-ade-foo"]

    def test_mixed_empty_and_non_empty_projects_sort_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = Path(tmp) / "projects"
            projects_dir.mkdir()
            empty = projects_dir / "-Users-ade-empty"
            full = projects_dir / "C--Users-Moho-project"
            empty.mkdir()
            full.mkdir()
            (full / "session.jsonl").write_text(
                '{"type":"user","timestamp":"2025-01-01T00:00:00Z","message":{"content":"hi"}}\n'
            )
            with patch("claude_history_explorer.projects.get_projects_dir",
                       return_value=projects_dir):
                projects = list_projects()
                assert [project.name for project in projects] == [
                    "C--Users-Moho-project",
                    "-Users-ade-empty",
                ]


# ---------------------------------------------------------------------------
# Issues 2-4: _decode_project_path — Unix root, drive letters, fallback sep
# ---------------------------------------------------------------------------

class TestDecodeProjectPath:
    """_decode_project_path must handle both Unix and Windows encoded names."""

    def test_unix_path_fallback(self):
        result = Project._decode_project_path("-Users-ade-projects-foo")
        assert result == "/Users/ade/projects/foo"

    def test_windows_drive_letter_detected(self):
        result = Project._decode_project_path("C--Users-Moho-project")
        assert result.startswith("C:")

    def test_windows_drive_letter_components(self):
        result = Project._decode_project_path("C--Users-Moho-project")
        parts = result.replace("\\", "/").split("/")
        assert parts[-1] == "project"
        assert "Moho" in parts

    def test_windows_d_drive(self):
        result = Project._decode_project_path("D--dev-myapp")
        assert result.startswith("D:")
        parts = result.replace("\\", "/").split("/")
        assert "dev" in parts
        assert "myapp" in parts

    def test_windows_lowercase_drive(self):
        result = Project._decode_project_path("c--Users-Moho-project")
        assert result[0].upper() == "C"
        assert result[1] == ":"

    def test_fallback_does_not_use_hardcoded_slash(self):
        result = Project._decode_project_path("C--NoSuchDir-child")
        assert result.startswith("C:/"), f"Expected C:/ prefix, got {result}"
        assert "\\" not in result, f"Unexpected backslash in {result}"

    def test_unix_still_works(self):
        """Existing Unix behavior must not regress."""
        result = Project._decode_project_path("-nonexistent-path-here")
        assert result == "/nonexistent/path/here"

    def test_unc_path(self):
        """UNC paths like \\\\server\\share encode as --server-share."""
        result = Project._decode_project_path("--server-share-project")
        assert "server" in result
        assert "share" in result

    def test_empty_string(self):
        result = Project._decode_project_path("")
        assert result  # should not crash or return empty

    def test_single_component(self):
        result = Project._decode_project_path("project")
        assert "project" in result

    def test_trailing_dash(self):
        result = Project._decode_project_path("-Users-ade-project-")
        assert "project" in result

    def test_existing_dotted_path_component_is_preserved(self, tmp_path):
        target = tmp_path / "foo.bar"
        target.mkdir()
        encoded = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in str(target))

        assert Project._decode_project_path(encoded) == str(target)

    def test_existing_spaced_path_component_is_preserved(self, tmp_path):
        target = tmp_path / "foo bar"
        target.mkdir()
        encoded = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in str(target))

        assert Project._decode_project_path(encoded) == str(target)


# ---------------------------------------------------------------------------
# Issues 5-7: short_name / basename — split("/") fails on Windows paths
# ---------------------------------------------------------------------------

class TestProjectNameExtraction:
    """short_name and display helpers must work with any path separator."""

    def test_short_name_unix_path(self):
        p = Project(name="x", path="/Users/ade/my_project",
                    dir_path=Path("."), session_files=[])
        assert p.short_name == "My Project"

    def test_short_name_windows_path(self):
        p = Project(name="x", path="C:/Users/Moho/my_project",
                    dir_path=Path("."), session_files=[])
        assert p.short_name == "My Project"

    def test_short_name_windows_backslash_path(self):
        p = Project(name="x", path="C:\\Users\\Moho\\my_project",
                    dir_path=Path("."), session_files=[])
        assert p.short_name == "My Project"

    def test_basename_unix(self):
        p = Project(name="x", path="/Users/ade/my_project",
                    dir_path=Path("."), session_files=[])
        assert p.basename == "my_project"

    def test_basename_windows(self):
        p = Project(name="x", path="C:/Users/Moho/my_project",
                    dir_path=Path("."), session_files=[])
        assert p.basename == "my_project"

    def test_basename_windows_backslash(self):
        p = Project(name="x", path="C:\\Users\\Moho\\my_project",
                    dir_path=Path("."), session_files=[])
        assert p.basename == "my_project"

    def test_basename_root_path(self):
        p = Project(name="x", path="/", dir_path=Path("."), session_files=[])
        assert p.basename  # should not be empty

    def test_basename_empty_path(self):
        p = Project(name="x", path="", dir_path=Path("."), session_files=[])
        assert p.basename  # should fall back to encoded name

    def test_short_name_empty_path(self):
        p = Project(name="encoded-name", path="", dir_path=Path("."), session_files=[])
        assert p.short_name  # should not be empty


# ---------------------------------------------------------------------------
# Issue 8: Console encoding guard
# ---------------------------------------------------------------------------

class TestConsoleEncoding:
    """The encoding guard must not crash when stdout is not a TextIOWrapper."""

    def test_reconfigure_guard_does_not_crash_on_non_text_stream(self):
        """_ensure_utf8_output must not raise when stdout lacks reconfigure."""
        import io
        from claude_history_explorer.cli import _ensure_utf8_output

        fake_stdout = io.BytesIO()
        with patch("sys.stdout", fake_stdout), \
             patch("sys.stderr", fake_stdout), \
             patch("sys.platform", "win32"):
            _ensure_utf8_output()

    def test_reconfigure_called_on_win32(self):
        """_ensure_utf8_output must call reconfigure on win32."""
        from unittest.mock import MagicMock
        from claude_history_explorer.cli import _ensure_utf8_output

        fake_out = MagicMock()
        fake_err = MagicMock()
        with patch("sys.stdout", fake_out), \
             patch("sys.stderr", fake_err), \
             patch("sys.platform", "win32"):
            _ensure_utf8_output()
        fake_out.reconfigure.assert_called_once_with(
            encoding="utf-8", errors="replace"
        )
        fake_err.reconfigure.assert_called_once_with(
            encoding="utf-8", errors="replace"
        )

    def test_no_reconfigure_on_non_win32(self):
        """_ensure_utf8_output must be a no-op on non-Windows."""
        import io
        from claude_history_explorer.cli import _ensure_utf8_output

        fake_stream = io.StringIO()
        called = []
        fake_stream.reconfigure = lambda **kw: called.append(kw)
        with patch("sys.stdout", fake_stream), \
             patch("sys.stderr", fake_stream), \
             patch("sys.platform", "linux"):
            _ensure_utf8_output()
        assert len(called) == 0


# ---------------------------------------------------------------------------
# Integration: cli.py display must use Project properties, not split('/')
# ---------------------------------------------------------------------------

class TestCliDisplayAbstraction:
    """cli.py must not contain path.split('/') — it should use Project
    properties instead."""

    def test_no_raw_path_split_in_cli(self):
        cli_path = Path(__file__).parent.parent / "claude_history_explorer" / "cli.py"
        source = cli_path.read_text()
        matches = re.findall(r"""\.path\.split\s*\(\s*['"]\/['"]\s*\)""", source)
        assert matches == [], (
            f"Found {len(matches)} raw path.split('/') call(s) in cli.py — "
            "use Project.short_name or Project.basename instead"
        )
