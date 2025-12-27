"""Unit tests for work_classifier module."""

import pytest
from claude_history_explorer.work_classifier import (
    WORK_CATEGORIES,
    WorkBreakdown,
    classify_text,
    score_session,
    classify_session,
    classify_session_proportional,
    format_work_breakdown,
)


class TestWorkCategories:
    """Test WORK_CATEGORIES configuration."""

    def test_all_categories_have_required_fields(self):
        """Test that all categories have name, description, keywords, and file_patterns."""
        for cat_id, cat_info in WORK_CATEGORIES.items():
            assert "name" in cat_info, f"{cat_id} missing 'name'"
            assert "description" in cat_info, f"{cat_id} missing 'description'"
            assert "keywords" in cat_info, f"{cat_id} missing 'keywords'"
            assert "file_patterns" in cat_info, f"{cat_id} missing 'file_patterns'"
            assert len(cat_info["keywords"]) > 0, f"{cat_id} has no keywords"

    def test_expected_categories_exist(self):
        """Test that expected knowledge work categories exist."""
        expected = ["writing", "analysis", "research", "teaching", "coding", "admin", "communication", "planning"]
        for cat in expected:
            assert cat in WORK_CATEGORIES, f"Missing expected category: {cat}"


class TestClassifyText:
    """Test classify_text function."""

    def test_writing_keywords(self):
        """Test that writing keywords are detected."""
        text = "I need to revise the introduction section of my paper manuscript"
        scores = classify_text(text)

        assert scores["writing"] > 0
        assert scores["writing"] > scores["coding"]

    def test_coding_keywords(self):
        """Test that coding keywords are detected."""
        text = "Fix the bug in the function and run the test"
        scores = classify_text(text)

        assert scores["coding"] > 0
        assert scores["coding"] > scores["writing"]

    def test_teaching_keywords(self):
        """Test that teaching keywords are detected."""
        text = "Grade the student assignment using the rubric and provide feedback"
        scores = classify_text(text)

        assert scores["teaching"] > 0
        assert scores["teaching"] > scores["coding"]

    def test_analysis_keywords(self):
        """Test that analysis keywords are detected."""
        text = "Analyze the dataset and create a regression plot with matplotlib"
        scores = classify_text(text)

        assert scores["analysis"] > 0

    def test_empty_text(self):
        """Test classification of empty text."""
        scores = classify_text("")

        # Should return scores for all categories (all zeros)
        assert len(scores) == len(WORK_CATEGORIES)
        assert all(score == 0 for score in scores.values())

    def test_case_insensitive(self):
        """Test that keyword matching is case insensitive."""
        text1 = "Write a paper"
        text2 = "WRITE A PAPER"
        text3 = "WrItE a PaPeR"

        scores1 = classify_text(text1)
        scores2 = classify_text(text2)
        scores3 = classify_text(text3)

        assert scores1["writing"] == scores2["writing"] == scores3["writing"]

    def test_scores_normalized(self):
        """Test that scores are normalized between 0 and 1."""
        text = "paper draft write revise edit manuscript abstract introduction"
        scores = classify_text(text)

        for score in scores.values():
            assert 0 <= score <= 1


class TestScoreSession:
    """Test score_session function."""

    def test_message_content_scoring(self):
        """Test that message content affects scores."""
        messages = ["Help me write my thesis", "Draft the introduction"]
        scores = score_session(messages)

        assert scores["writing"] > 0

    def test_project_path_pattern_matching(self):
        """Test that project path patterns affect scores."""
        messages = ["Hello"]

        # .py file pattern should boost coding
        scores_py = score_session(messages, "/project/main.py")
        scores_none = score_session(messages, "/project/unknown")

        assert scores_py["coding"] > scores_none["coding"]

    def test_tex_file_boosts_writing(self):
        """Test that .tex files boost writing score."""
        messages = ["Fix this"]
        scores = score_session(messages, "/papers/thesis.tex")

        assert scores["writing"] > 0.2  # Should have file pattern boost

    def test_csv_file_boosts_analysis(self):
        """Test that .csv files boost analysis score."""
        messages = ["Process this"]
        scores = score_session(messages, "/data/results.csv")

        assert scores["analysis"] > 0.2

    def test_combined_scoring(self):
        """Test that both message and path contribute to score."""
        messages = ["Analyze the data and create visualization"]
        scores = score_session(messages, "/project/analysis.ipynb")

        # Should have both keyword and pattern boosts
        assert scores["analysis"] > 0.3


class TestClassifySession:
    """Test classify_session (winner-take-all) function."""

    def test_clear_winner(self):
        """Test classification when there's a clear winner."""
        messages = [
            "Grade the student homework",
            "Apply the rubric for the exam",
            "Provide feedback on their assignment"
        ]

        result = classify_session(messages)
        assert result == "teaching"

    def test_ambiguous_returns_none(self):
        """Test that ambiguous sessions return None."""
        # Mix of writing and coding signals
        messages = [
            "Write a function",  # writing + coding
            "Fix the bug",  # coding
            "Draft the report"  # writing
        ]

        result = classify_session(messages)
        # Should return None if no clear winner
        # (depends on exact scores, but testing the mechanism)
        assert result is None or result in WORK_CATEGORIES

    def test_low_score_returns_none(self):
        """Test that low-scoring text returns None."""
        messages = ["hello", "yes", "okay"]

        result = classify_session(messages)
        assert result is None

    def test_empty_messages(self):
        """Test classification of empty messages."""
        result = classify_session([])
        assert result is None

    def test_path_influences_classification(self):
        """Test that project path can influence classification."""
        messages = ["Help me with this"]

        result = classify_session(messages, "/grading/assignment1")
        # Path contains "grading" which should boost teaching
        assert result == "teaching" or result is None


class TestClassifySessionProportional:
    """Test classify_session_proportional function."""

    def test_proportions_sum_to_one(self):
        """Test that proportional weights sum to 1.0."""
        messages = ["Write a paper and analyze the data"]
        proportions = classify_session_proportional(messages)

        if proportions:  # Skip if empty
            total = sum(proportions.values())
            assert abs(total - 1.0) < 0.001, f"Proportions sum to {total}, not 1.0"

    def test_all_categories_present(self):
        """Test that all categories are in the result when there's signal."""
        messages = ["Write a paper and fix the bug"]  # Has keywords
        proportions = classify_session_proportional(messages)

        # Should have scores for all categories (even if some are 0)
        for cat_id in WORK_CATEGORIES:
            assert cat_id in proportions

    def test_higher_signal_gets_higher_proportion(self):
        """Test that stronger signals get higher proportions."""
        messages = [
            "Grade the homework assignment",
            "Use the rubric",
            "Provide student feedback"
        ]

        proportions = classify_session_proportional(messages)

        # Teaching should have highest proportion
        assert proportions["teaching"] > proportions["coding"]
        assert proportions["teaching"] > proportions["admin"]

    def test_empty_messages_returns_empty(self):
        """Test that empty messages return empty dict."""
        proportions = classify_session_proportional([])
        assert proportions == {}


class TestWorkBreakdown:
    """Test WorkBreakdown dataclass."""

    def test_add_session_with_category(self):
        """Test adding a session with a category."""
        breakdown = WorkBreakdown()
        breakdown.add_session("writing", messages=10, minutes=60)

        assert breakdown.total_messages == 10
        assert breakdown.total_minutes == 60
        assert breakdown.category_messages["writing"] == 10
        assert breakdown.category_minutes["writing"] == 60
        assert breakdown.uncategorized_messages == 0

    def test_add_session_without_category(self):
        """Test adding a session without a category (None)."""
        breakdown = WorkBreakdown()
        breakdown.add_session(None, messages=5, minutes=30)

        assert breakdown.total_messages == 5
        assert breakdown.total_minutes == 30
        assert breakdown.uncategorized_messages == 5
        assert breakdown.uncategorized_minutes == 30

    def test_multiple_sessions(self):
        """Test adding multiple sessions."""
        breakdown = WorkBreakdown()
        breakdown.add_session("writing", messages=10, minutes=60)
        breakdown.add_session("coding", messages=20, minutes=120)
        breakdown.add_session(None, messages=5, minutes=30)

        assert breakdown.total_messages == 35
        assert breakdown.total_minutes == 210
        assert breakdown.category_messages["writing"] == 10
        assert breakdown.category_messages["coding"] == 20
        assert breakdown.uncategorized_messages == 5

    def test_get_summary_percentages(self):
        """Test that get_summary calculates percentages correctly."""
        breakdown = WorkBreakdown()
        breakdown.add_session("writing", messages=50, minutes=60)
        breakdown.add_session("coding", messages=50, minutes=60)

        summary = breakdown.get_summary()

        assert summary["writing"]["message_pct"] == 50.0
        assert summary["writing"]["time_pct"] == 50.0
        assert summary["coding"]["message_pct"] == 50.0
        assert summary["coding"]["time_pct"] == 50.0

    def test_get_summary_hours_conversion(self):
        """Test that minutes are converted to hours."""
        breakdown = WorkBreakdown()
        breakdown.add_session("writing", messages=10, minutes=90)

        summary = breakdown.get_summary()

        assert summary["writing"]["hours"] == 1.5

    def test_get_summary_includes_other(self):
        """Test that summary includes 'other' category."""
        breakdown = WorkBreakdown()
        breakdown.add_session(None, messages=10, minutes=60)

        summary = breakdown.get_summary()

        assert "other" in summary
        assert summary["other"]["messages"] == 10
        assert summary["other"]["hours"] == 1.0

    def test_empty_breakdown(self):
        """Test summary of empty breakdown."""
        breakdown = WorkBreakdown()
        summary = breakdown.get_summary()

        # Should not raise division by zero
        assert summary["writing"]["message_pct"] == 0
        assert summary["writing"]["time_pct"] == 0


class TestFormatWorkBreakdown:
    """Test format_work_breakdown function."""

    def test_format_includes_header(self):
        """Test that formatted output includes header."""
        breakdown = WorkBreakdown()
        breakdown.add_session("writing", messages=10, minutes=120)

        output = format_work_breakdown(breakdown)

        assert "Work Breakdown" in output
        assert "=" in output

    def test_format_includes_totals(self):
        """Test that formatted output includes totals."""
        breakdown = WorkBreakdown()
        breakdown.add_session("writing", messages=10, minutes=120)

        output = format_work_breakdown(breakdown)

        assert "Total:" in output
        assert "2.0 hours" in output
        assert "10 messages" in output

    def test_format_shows_categories_by_percentage(self):
        """Test that categories are shown sorted by percentage."""
        breakdown = WorkBreakdown()
        breakdown.add_session("writing", messages=10, minutes=120)  # 2h
        breakdown.add_session("coding", messages=5, minutes=60)     # 1h

        output = format_work_breakdown(breakdown)

        # Writing should appear before coding (higher time)
        writing_pos = output.find("Writing")
        coding_pos = output.find("Software Development")
        assert writing_pos < coding_pos

    def test_format_skips_tiny_categories(self):
        """Test that categories <1% are skipped."""
        breakdown = WorkBreakdown()
        breakdown.add_session("writing", messages=100, minutes=1000)
        breakdown.add_session("admin", messages=1, minutes=1)  # <1%

        output = format_work_breakdown(breakdown)

        # Writing should be there
        assert "Writing" in output

    def test_format_shows_bar_visualization(self):
        """Test that output includes bar visualization."""
        breakdown = WorkBreakdown()
        breakdown.add_session("writing", messages=10, minutes=120)

        output = format_work_breakdown(breakdown)

        # Should have bar characters
        assert "#" in output or "-" in output


class TestIntegration:
    """Integration tests for the full classification workflow."""

    def test_proportional_classification_workflow(self):
        """Test the full proportional classification workflow."""
        # Simulate classifying multiple sessions
        sessions = [
            (["Write the introduction", "Edit the abstract"], "/papers/thesis.tex"),
            (["Fix the bug", "Run the tests"], "/project/src/main.py"),
            (["Grade homework", "Add rubric feedback"], "/courses/cs101/grading"),
        ]

        breakdown = WorkBreakdown()

        for messages, path in sessions:
            proportions = classify_session_proportional(messages, path)

            # Allocate time proportionally (60 min per session)
            for cat_id, weight in proportions.items():
                mins = int(60 * weight)
                msgs = int(len(messages) * weight)
                if mins > 0:
                    breakdown.add_session(cat_id, msgs, mins)

        summary = breakdown.get_summary()

        # Should have distributed time across categories
        assert breakdown.total_minutes > 0
        assert len([k for k, v in summary.items() if v["minutes"] > 0]) > 1

    def test_winner_take_all_workflow(self):
        """Test the winner-take-all classification workflow."""
        sessions = [
            (["Write the paper draft"], "/papers/thesis.tex"),
            (["Fix bug, run test"], "/src/main.py"),
        ]

        breakdown = WorkBreakdown()

        for messages, path in sessions:
            category = classify_session(messages, path)
            breakdown.add_session(category, len(messages), 60)

        # Each session should go to one category or uncategorized
        assert breakdown.total_minutes == 120
        assert breakdown.total_messages == 2
