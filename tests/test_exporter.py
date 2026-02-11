"""Tests for CSV exporter."""

import csv
import io
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from polyglott.parser import POEntryData
from polyglott.exporter import export_to_csv
from polyglott.linter import Severity, Violation


class TestExporter:
    """Test suite for CSV exporter."""

    def test_export_single_file_schema(self):
        """Test CSV schema for single-file mode."""
        entries = [
            POEntryData(
                msgid="Hello",
                msgstr="Hallo",
                msgctxt=None,
                extracted_comments="Test comment",
                translator_comments="",
                references="main.py:10",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file=None
            )
        ]

        output = io.StringIO()
        # Redirect stdout temporarily
        old_stdout = sys.stdout
        sys.stdout = output
        export_to_csv(entries)
        sys.stdout = old_stdout

        # Parse CSV output
        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)

        # Check schema
        expected_columns = [
            "msgid", "msgstr", "msgctxt",
            "extracted_comments", "translator_comments", "references",
            "fuzzy", "obsolete", "is_plural", "plural_index"
        ]
        assert list(rows[0].keys()) == expected_columns

        # Check data
        assert rows[0]["msgid"] == "Hello"
        assert rows[0]["msgstr"] == "Hallo"
        assert rows[0]["fuzzy"] == "False"

    def test_export_multi_file_schema(self):
        """Test CSV schema for multi-file mode."""
        entries = [
            POEntryData(
                msgid="Hello",
                msgstr="Hallo",
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
        ]

        output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = output
        export_to_csv(entries, multi_file=True)
        sys.stdout = old_stdout

        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)

        # Check that source_file is first column
        columns = list(rows[0].keys())
        assert columns[0] == "source_file"
        assert rows[0]["source_file"] == "test.po"

    def test_export_unicode_content(self):
        """Test handling of Unicode characters in CSV."""
        entries = [
            POEntryData(
                msgid="German",
                msgstr="Äpfel, Öfen, Straße",
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
            ),
            POEntryData(
                msgid="Emoji",
                msgstr="🎉 🚀 ❤️",
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
            )
        ]

        output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = output
        export_to_csv(entries)
        sys.stdout = old_stdout

        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)

        # Check Unicode is preserved
        assert rows[0]["msgstr"] == "Äpfel, Öfen, Straße"
        assert rows[1]["msgstr"] == "🎉 🚀 ❤️"

    def test_export_csv_escaping(self):
        """Test CSV escaping of special characters."""
        entries = [
            POEntryData(
                msgid='Test "quotes" and commas, here',
                msgstr='Result with "quotes", commas, and\nnewlines',
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
            )
        ]

        output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = output
        export_to_csv(entries)
        sys.stdout = old_stdout

        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)

        # CSV reader should handle escaping automatically
        assert 'quotes' in rows[0]["msgid"]
        assert 'commas' in rows[0]["msgid"]
        assert 'newlines' in rows[0]["msgstr"]

    def test_export_sorting(self):
        """Test sorting by different fields."""
        entries = [
            POEntryData("Zebra", "Z", None, "", "", "", False, False, False, None),
            POEntryData("Apple", "A", None, "", "", "", False, False, False, None),
            POEntryData("Mango", "M", None, "", "", "", False, False, False, None),
        ]

        output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = output
        export_to_csv(entries, sort_by="msgid")
        sys.stdout = old_stdout

        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)

        # Check sorting
        assert rows[0]["msgid"] == "Apple"
        assert rows[1]["msgid"] == "Mango"
        assert rows[2]["msgid"] == "Zebra"

    def test_export_to_file(self):
        """Test exporting to a file."""
        entries = [
            POEntryData("Hello", "Hallo", None, "", "", "", False, False, False, None),
        ]

        with NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            output_file = f.name

        try:
            export_to_csv(entries, output_file=output_file)

            # Read back and verify
            with open(output_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 1
            assert rows[0]["msgid"] == "Hello"
            assert rows[0]["msgstr"] == "Hallo"
        finally:
            Path(output_file).unlink()

    def test_export_empty_dataframe(self):
        """Test exporting empty entry list."""
        output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = output
        export_to_csv([])
        sys.stdout = old_stdout

        output.seek(0)
        content = output.read()

        # Should have headers but no data rows
        lines = content.strip().split('\n')
        assert len(lines) == 1  # Header only
        assert "msgid" in lines[0]

    def test_invalid_sort_field(self):
        """Test error handling for invalid sort field."""
        entries = [
            POEntryData("Test", "Test", None, "", "", "", False, False, False, None),
        ]

        with pytest.raises(ValueError, match="Invalid sort field"):
            export_to_csv(entries, sort_by="nonexistent_field")


class TestLintMode:
    """Test suite for lint mode CSV export."""

    def test_lint_mode_schema(self):
        """Test CSV schema for lint mode."""
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

        violation = Violation(
            entry=entry,
            severity=Severity.ERROR,
            check_name="untranslated",
            message="Entry is not translated"
        )

        output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = output
        export_to_csv([], lint_mode=True, violations=[violation])
        sys.stdout = old_stdout

        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)

        # Check schema includes lint columns
        columns = list(rows[0].keys())
        assert "severity" in columns
        assert "check" in columns
        assert "message" in columns

        # Check data
        assert rows[0]["msgid"] == "Test"
        assert rows[0]["severity"] == "error"
        assert rows[0]["check"] == "untranslated"
        assert rows[0]["message"] == "Entry is not translated"

    def test_lint_mode_multi_file_schema(self):
        """Test CSV schema for lint mode with multi-file."""
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

        violation = Violation(
            entry=entry,
            severity=Severity.WARNING,
            check_name="fuzzy",
            message="Entry is marked as fuzzy"
        )

        output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = output
        export_to_csv([], lint_mode=True, violations=[violation], multi_file=True)
        sys.stdout = old_stdout

        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)

        # Check source_file is first column
        columns = list(rows[0].keys())
        assert columns[0] == "source_file"
        assert rows[0]["source_file"] == "test.po"

    def test_lint_mode_multiple_violations(self):
        """Test lint mode with multiple violations."""
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
            source_file=None
        )

        entry2 = POEntryData(
            msgid="Test2",
            msgstr="Test",
            msgctxt=None,
            extracted_comments="",
            translator_comments="",
            references="",
            fuzzy=True,
            obsolete=False,
            is_plural=False,
            plural_index=None,
            source_file=None
        )

        violations = [
            Violation(entry1, Severity.ERROR, "untranslated", "Entry is not translated"),
            Violation(entry2, Severity.WARNING, "fuzzy", "Entry is marked as fuzzy"),
        ]

        output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = output
        export_to_csv([], lint_mode=True, violations=violations)
        sys.stdout = old_stdout

        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)

        # Should have two rows (one per violation)
        assert len(rows) == 2
        assert rows[0]["severity"] == "error"
        assert rows[1]["severity"] == "warning"

    def test_lint_mode_empty_violations(self):
        """Test lint mode with no violations."""
        output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = output
        export_to_csv([], lint_mode=True, violations=[])
        sys.stdout = old_stdout

        output.seek(0)
        content = output.read()

        # Should have headers but no data rows
        lines = content.strip().split('\n')
        assert len(lines) == 1  # Header only
        assert "severity" in lines[0]
        assert "check" in lines[0]
        assert "message" in lines[0]

    def test_lint_mode_without_violations_raises_error(self):
        """Test that lint mode requires violations parameter."""
        with pytest.raises(ValueError, match="violations required"):
            export_to_csv([], lint_mode=True)

    def test_lint_mode_all_severity_levels(self):
        """Test lint mode with all severity levels."""
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
            source_file=None
        )

        violations = [
            Violation(entry, Severity.ERROR, "error_check", "Error"),
            Violation(entry, Severity.WARNING, "warning_check", "Warning"),
            Violation(entry, Severity.INFO, "info_check", "Info"),
        ]

        output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = output
        export_to_csv([], lint_mode=True, violations=violations)
        sys.stdout = old_stdout

        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)

        assert len(rows) == 3
        assert rows[0]["severity"] == "error"
        assert rows[1]["severity"] == "warning"
        assert rows[2]["severity"] == "info"
