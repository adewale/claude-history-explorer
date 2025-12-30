"""Tests for work type classification."""

import pytest
from claude_history_explorer.history import (
    classify_project,
    get_work_type_name,
    WORK_TYPE_PATTERNS,
    WORK_TYPE_INFO,
)


class TestClassifyProject:
    """Test project classification by path."""

    # === Positive tests: paths that SHOULD match ===

    def test_papers_directory_is_writing(self):
        assert classify_project("/Users/me/papers/thesis") == "writing"

    def test_tex_extension_is_writing(self):
        assert classify_project("/project/paper.tex") == "writing"

    def test_docs_directory_is_writing(self):
        assert classify_project("/Users/me/docs/manual") == "writing"

    def test_terminal_thesis_is_writing(self):
        # Terminal directory without trailing slash
        assert classify_project("/Users/me/thesis") == "writing"
        assert classify_project("/Users/me/thesis/") == "writing"

    def test_data_directory_is_analysis(self):
        assert classify_project("/Users/me/data/experiment") == "analysis"

    def test_ipynb_extension_is_analysis(self):
        assert classify_project("/project/notebook.ipynb") == "analysis"

    def test_csv_extension_is_analysis(self):
        assert classify_project("/project/results.csv") == "analysis"

    def test_research_directory_is_research(self):
        assert classify_project("/Users/me/research/lit-review") == "research"

    def test_bib_extension_is_research(self):
        assert classify_project("/project/references.bib") == "research"

    def test_course_directory_is_teaching(self):
        assert classify_project("/Users/me/courses/cs101") == "teaching"

    def test_grading_directory_is_teaching(self):
        assert classify_project("/work/grading/hw1") == "teaching"

    def test_design_directory_is_design(self):
        assert classify_project("/Users/me/design/app-mockups") == "design"

    def test_figma_extension_is_design(self):
        assert classify_project("/project/components.fig") == "design"

    def test_ui_directory_is_design(self):
        assert classify_project("/Users/me/ui/dashboard") == "design"

    def test_default_is_coding(self):
        assert classify_project("/Users/me/code/myapp") == "coding"
        assert classify_project("/random/project") == "coding"
        assert classify_project("/src/main.py") == "coding"

    def test_case_insensitive(self):
        assert classify_project("/PAPERS/THESIS") == "writing"
        assert classify_project("/Data/Results") == "analysis"

    # === Negative tests: paths that should NOT false-positive ===

    def test_no_false_positive_on_partial_match(self):
        # "thesis" should not match inside "synthesis"
        assert classify_project("/Users/me/synthesis-project") == "coding"
        # "data" should not match inside "metadata"
        assert classify_project("/Users/me/metadata-service") == "coding"

    def test_no_false_positive_on_extension_substring(self):
        # ".tex" should not match ".texture" or ".text"
        assert classify_project("/project/file.texture") == "coding"
        # ".csv" should not match ".csvx"
        assert classify_project("/project/file.csvx") == "coding"

    def test_mid_path_requires_slashes(self):
        # "/data/" requires slashes on both sides for mid-path
        assert classify_project("/mydata/project") == "coding"  # no leading slash before "data"
        assert classify_project("/project/database") == "coding"  # "data" is substring


class TestWorkTypeInfo:
    """Test work type metadata."""

    def test_all_types_have_info(self):
        for work_type in ["coding", "writing", "analysis", "research", "teaching", "design"]:
            assert work_type in WORK_TYPE_INFO
            assert "name" in WORK_TYPE_INFO[work_type]
            assert "description" in WORK_TYPE_INFO[work_type]

    def test_get_work_type_name(self):
        assert get_work_type_name("coding") == "Software Development"
        assert get_work_type_name("writing") == "Writing & Documentation"
        assert get_work_type_name("unknown") == "Unknown"  # Fallback

    def test_all_pattern_types_have_info(self):
        """Ensure every type in WORK_TYPE_PATTERNS has corresponding info."""
        for work_type in WORK_TYPE_PATTERNS.keys():
            assert work_type in WORK_TYPE_INFO, f"{work_type} has patterns but no info"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_path(self):
        assert classify_project("") == "coding"

    def test_root_path(self):
        assert classify_project("/") == "coding"

    def test_path_with_multiple_matches(self):
        # First match wins (writing patterns checked before analysis)
        # This tests pattern priority - writing checked first
        path = "/Users/me/papers/data/notebook.ipynb"
        result = classify_project(path)
        # Papers directory should match writing first
        assert result == "writing"

    def test_deeply_nested_paths(self):
        assert classify_project("/a/b/c/d/e/f/papers/thesis") == "writing"
        assert classify_project("/a/b/c/d/e/f/data/results") == "analysis"

    def test_windows_style_paths(self):
        # Should work with forward slashes even on Windows paths
        assert classify_project("C:/Users/me/papers/thesis") == "writing"
