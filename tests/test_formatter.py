"""Tests for the formatter module."""

import pytest

from polyglott.formatter import format_text_output, _extract_line_number
from polyglott.linter import Severity, Violation
from polyglott.parser import POEntryData


@pytest.fixture
def sample_entry():
    """Create a sample entry."""
    return POEntryData(
        msgid="Test",
        msgstr="",
        msgctxt=None,
        extracted_comments="",
        translator_comments="",
        references="file.py:42",
        fuzzy=False,
        obsolete=False,
        is_plural=False,
        plural_index=None,
        source_file="test.po"
    )


@pytest.fixture
def sample_violation(sample_entry):
    """Create a sample violation."""
    return Violation(
        entry=sample_entry,
        severity=Severity.ERROR,
        check_name="untranslated",
        message="Entry is not translated"
    )


class TestExtractLineNumber:
    """Test line number extraction."""

    def test_extract_line_number_single_reference(self):
        """Test extracting line number from single reference."""
        line_num = _extract_line_number("file.py:42")
        assert line_num == "42"

    def test_extract_line_number_multiple_references(self):
        """Test extracting line number from multiple references."""
        line_num = _extract_line_number("file1.py:10 file2.py:20")
        assert line_num == "10"

    def test_extract_line_number_no_line(self):
        """Test extracting line number when none exists."""
        line_num = _extract_line_number("file.py")
        assert line_num == ""

    def test_extract_line_number_empty(self):
        """Test extracting line number from empty string."""
        line_num = _extract_line_number("")
        assert line_num == ""


class TestFormatTextOutput:
    """Test text output formatting."""

    def test_format_no_violations(self):
        """Test formatting with no violations."""
        output = format_text_output([])
        assert "No issues found" in output

    def test_format_single_violation(self, sample_violation):
        """Test formatting a single violation."""
        output = format_text_output([sample_violation])
        assert "test.po:" in output
        assert "ERROR" in output
        assert "line 42" in output
        assert "untranslated" in output
        assert "Entry is not translated" in output
        assert "1 error" in output
        assert "1 issue in 1 file" in output

    def test_format_multiple_violations(self):
        """Test formatting multiple violations."""
        entry1 = POEntryData(
            msgid="Test1",
            msgstr="",
            msgctxt=None,
            extracted_comments="",
            translator_comments="",
            references="file.py:10",
            fuzzy=False,
            obsolete=False,
            is_plural=False,
            plural_index=None,
            source_file="test1.po"
        )

        entry2 = POEntryData(
            msgid="Test2",
            msgstr="Test",
            msgctxt=None,
            extracted_comments="",
            translator_comments="",
            references="file.py:20",
            fuzzy=True,
            obsolete=False,
            is_plural=False,
            plural_index=None,
            source_file="test2.po"
        )

        violations = [
            Violation(entry1, Severity.ERROR, "untranslated", "Entry is not translated"),
            Violation(entry2, Severity.WARNING, "fuzzy", "Entry is marked as fuzzy"),
        ]

        output = format_text_output(violations)
        assert "test1.po:" in output
        assert "test2.po:" in output
        assert "ERROR" in output
        assert "WARNING" in output
        assert "1 error, 1 warning" in output
        assert "2 issues in 2 files" in output

    def test_format_groups_by_file(self):
        """Test that violations are grouped by source file."""
        entry1 = POEntryData(
            msgid="Test1",
            msgstr="",
            msgctxt=None,
            extracted_comments="",
            translator_comments="",
            references="file.py:10",
            fuzzy=False,
            obsolete=False,
            is_plural=False,
            plural_index=None,
            source_file="same.po"
        )

        entry2 = POEntryData(
            msgid="Test2",
            msgstr="",
            msgctxt=None,
            extracted_comments="",
            translator_comments="",
            references="file.py:20",
            fuzzy=False,
            obsolete=False,
            is_plural=False,
            plural_index=None,
            source_file="same.po"
        )

        violations = [
            Violation(entry1, Severity.ERROR, "untranslated", "Entry is not translated"),
            Violation(entry2, Severity.ERROR, "untranslated", "Entry is not translated"),
        ]

        output = format_text_output(violations)
        # Should only have one file header
        assert output.count("same.po:") == 1
        # But two violations
        assert output.count("ERROR") == 2
        assert "2 errors" in output
        assert "2 issues in 1 file" in output

    def test_format_all_severity_levels(self):
        """Test formatting with all severity levels."""
        entry = POEntryData(
            msgid="Test",
            msgstr="",
            msgctxt=None,
            extracted_comments="",
            translator_comments="",
            references="file.py:10",
            fuzzy=False,
            obsolete=False,
            is_plural=False,
            plural_index=None,
            source_file="test.po"
        )

        violations = [
            Violation(entry, Severity.ERROR, "error_check", "Error message"),
            Violation(entry, Severity.WARNING, "warning_check", "Warning message"),
            Violation(entry, Severity.INFO, "info_check", "Info message"),
        ]

        output = format_text_output(violations)
        assert "ERROR" in output
        assert "WARNING" in output
        assert "INFO" in output
        assert "1 error, 1 warning, 1 info" in output
        assert "3 issues in 1 file" in output

    def test_format_unknown_source_file(self):
        """Test formatting violation with no source file."""
        entry = POEntryData(
            msgid="Test",
            msgstr="",
            msgctxt=None,
            extracted_comments="",
            translator_comments="",
            references="file.py:10",
            fuzzy=False,
            obsolete=False,
            is_plural=False,
            plural_index=None,
            source_file=None
        )

        violation = Violation(entry, Severity.ERROR, "untranslated", "Entry is not translated")
        output = format_text_output([violation])
        assert "(unknown):" in output

    def test_format_no_line_number(self):
        """Test formatting violation with no line number."""
        entry = POEntryData(
            msgid="Test",
            msgstr="",
            msgctxt=None,
            extracted_comments="",
            translator_comments="",
            references="",
            fuzzy=False,
            obsolete=False,
            is_plural=False,
            plural_index=None,
            source_file="test.po"
        )

        violation = Violation(entry, Severity.ERROR, "untranslated", "Entry is not translated")
        output = format_text_output([violation])
        assert "test.po:" in output
        # Should still format properly without line number
        assert "ERROR" in output
        assert "untranslated" in output

    def test_format_sorted_by_file(self):
        """Test that files are sorted alphabetically."""
        entry1 = POEntryData(
            msgid="Test1",
            msgstr="",
            msgctxt=None,
            extracted_comments="",
            translator_comments="",
            references="",
            fuzzy=False,
            obsolete=False,
            is_plural=False,
            plural_index=None,
            source_file="zzz.po"
        )

        entry2 = POEntryData(
            msgid="Test2",
            msgstr="",
            msgctxt=None,
            extracted_comments="",
            translator_comments="",
            references="",
            fuzzy=False,
            obsolete=False,
            is_plural=False,
            plural_index=None,
            source_file="aaa.po"
        )

        violations = [
            Violation(entry1, Severity.ERROR, "untranslated", "Entry is not translated"),
            Violation(entry2, Severity.ERROR, "untranslated", "Entry is not translated"),
        ]

        output = format_text_output(violations)
        # aaa.po should appear before zzz.po
        aaa_pos = output.find("aaa.po:")
        zzz_pos = output.find("zzz.po:")
        assert aaa_pos < zzz_pos
