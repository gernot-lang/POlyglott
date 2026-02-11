"""Integration tests for CLI."""

import csv
import subprocess
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestCLI:
    """Test suite for CLI integration."""

    def test_version_flag(self):
        """Test --version flag."""
        result = subprocess.run(
            [sys.executable, "-m", "polyglott", "--version"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "0.1.0" in result.stdout

    def test_scan_single_file_to_stdout(self):
        """Test scanning a single file to stdout."""
        result = subprocess.run(
            [sys.executable, "-m", "polyglott", "scan", str(FIXTURES_DIR / "simple.po")],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0

        # Check CSV output
        lines = result.stdout.strip().split('\n')
        assert len(lines) > 1  # Header + data rows

        # Check statistics in stderr
        assert "Total entries: 4" in result.stderr
        assert "Untranslated: 2" in result.stderr

    def test_scan_single_file_to_file(self):
        """Test scanning a single file to output file."""
        with NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            output_file = f.name

        try:
            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "scan",
                    str(FIXTURES_DIR / "simple.po"),
                    "-o", output_file
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

            # Read and verify CSV
            with open(output_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 4
            assert any(row["msgid"] == "Hello" for row in rows)

        finally:
            Path(output_file).unlink()

    def test_scan_with_glob_patterns(self):
        """Test scanning multiple files with --include."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "scan",
                "--include", str(FIXTURES_DIR / "*.po"),
                "--exclude", str(FIXTURES_DIR / "malformed.po")
            ],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0

        # Should process multiple files
        assert "Files processed:" in result.stderr

        # Check CSV has source_file column
        lines = result.stdout.strip().split('\n')
        header = lines[0]
        assert "source_file" in header

    def test_scan_with_exclusions(self):
        """Test --exclude patterns."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "scan",
                "--include", str(FIXTURES_DIR / "*.po"),
                "--exclude", str(FIXTURES_DIR / "malformed.po")
            ],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0

        # Should succeed (no malformed file processed)
        assert "Files processed:" in result.stderr

    def test_scan_with_sorting(self):
        """Test --sort-by option."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "scan",
                str(FIXTURES_DIR / "simple.po"),
                "--sort-by", "msgid"
            ],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0

        # Parse CSV and check ordering
        lines = result.stdout.strip().split('\n')
        reader = csv.DictReader(lines)
        rows = list(reader)

        # Check that rows are sorted by msgid
        msgids = [row["msgid"] for row in rows]
        assert msgids == sorted(msgids)

    def test_scan_missing_file(self):
        """Test error handling for missing file."""
        result = subprocess.run(
            [sys.executable, "-m", "polyglott", "scan", "nonexistent.po"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 1
        assert "not found" in result.stderr.lower()

    def test_scan_no_args(self):
        """Test error when no file or --include specified."""
        result = subprocess.run(
            [sys.executable, "-m", "polyglott", "scan"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 1
        assert "Must specify either FILE or --include" in result.stderr

    def test_scan_conflicting_args(self):
        """Test error when both file and --include are specified."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "scan",
                str(FIXTURES_DIR / "simple.po"),
                "--include", "*.po"
            ],
            capture_output=True,
            text=True
        )

        assert result.returncode == 1
        assert "Cannot specify both" in result.stderr

    def test_unicode_preservation(self):
        """Test that Unicode is preserved in CSV output."""
        result = subprocess.run(
            [sys.executable, "-m", "polyglott", "scan", str(FIXTURES_DIR / "unicode.po")],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )

        assert result.returncode == 0

        # Check Unicode characters in output
        assert "Äpfel" in result.stdout
        assert "🎉" in result.stdout
        assert "你好" in result.stdout

    def test_help_command(self):
        """Test help output."""
        result = subprocess.run(
            [sys.executable, "-m", "polyglott", "--help"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "polyglott" in result.stdout
        assert "scan" in result.stdout
        assert "lint" in result.stdout


class TestLintCLI:
    """Test suite for lint subcommand."""

    def test_lint_single_file_csv(self):
        """Test linting a single file with CSV output."""
        result = subprocess.run(
            [sys.executable, "-m", "polyglott", "lint", str(FIXTURES_DIR / "format_issues.po")],
            capture_output=True,
            text=True
        )

        # Should find format issues (exit code 1 for errors)
        assert result.returncode == 1

        # Check CSV output
        lines = result.stdout.strip().split('\n')
        assert len(lines) > 1  # Header + data rows

        # Check for lint columns
        header = lines[0]
        assert "severity" in header
        assert "check" in header
        assert "message" in header

    def test_lint_single_file_text(self):
        """Test linting with text output."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "lint",
                str(FIXTURES_DIR / "format_issues.po"),
                "--format", "text"
            ],
            capture_output=True,
            text=True
        )

        assert result.returncode == 1

        # Check text format
        assert "format_issues.po:" in result.stdout
        assert "ERROR" in result.stdout
        assert "format_mismatch" in result.stdout

    def test_lint_with_glossary(self):
        """Test linting with glossary."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "lint",
                str(FIXTURES_DIR / "term_issues.po"),
                "--glossary", str(FIXTURES_DIR / "glossary.yaml"),
                "--format", "text"
            ],
            capture_output=True,
            text=True
        )

        # Should find term mismatches (exit code 2 for warnings only)
        assert result.returncode == 2

        # Check for term mismatch messages
        assert "term_mismatch" in result.stdout

    def test_lint_invalid_glossary(self):
        """Test error handling for invalid glossary."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "lint",
                str(FIXTURES_DIR / "simple.po"),
                "--glossary", str(FIXTURES_DIR / "glossary_invalid.yaml")
            ],
            capture_output=True,
            text=True
        )

        assert result.returncode == 1
        assert "Error loading glossary" in result.stderr

    def test_lint_nonexistent_glossary(self):
        """Test error handling for nonexistent glossary."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "lint",
                str(FIXTURES_DIR / "simple.po"),
                "--glossary", "nonexistent.yaml"
            ],
            capture_output=True,
            text=True
        )

        assert result.returncode == 1
        assert "Error loading glossary" in result.stderr

    def test_lint_severity_filter_error(self):
        """Test severity filtering (errors only)."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "lint",
                str(FIXTURES_DIR / "complex.po"),
                "--severity", "error",
                "--format", "text"
            ],
            capture_output=True,
            text=True
        )

        # Should only show errors
        if "ERROR" in result.stdout:
            # Should not show warnings
            assert "WARNING" not in result.stdout

    def test_lint_severity_filter_warning(self):
        """Test severity filtering (warnings and above)."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "lint",
                str(FIXTURES_DIR / "complex.po"),
                "--severity", "warning",
                "--format", "text"
            ],
            capture_output=True,
            text=True
        )

        # Should show warnings and errors, but not info
        if result.stdout.strip() and "issue" in result.stdout:
            # Verify info messages are excluded
            assert "obsolete" not in result.stdout.lower() or "INFO" not in result.stdout

    def test_lint_check_filter_include(self):
        """Test filtering checks with --check."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "lint",
                str(FIXTURES_DIR / "complex.po"),
                "--check", "untranslated",
                "--format", "text"
            ],
            capture_output=True,
            text=True
        )

        # Should only check for untranslated
        if result.returncode != 0:
            assert "untranslated" in result.stdout
            # Should not show other checks
            assert "fuzzy" not in result.stdout

    def test_lint_check_filter_exclude(self):
        """Test filtering checks with --no-check."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "lint",
                str(FIXTURES_DIR / "complex.po"),
                "--no-check", "obsolete",
                "--format", "text"
            ],
            capture_output=True,
            text=True
        )

        # Should not check for obsolete
        if result.stdout.strip():
            assert "obsolete" not in result.stdout

    def test_lint_multi_file_mode(self):
        """Test linting multiple files."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "lint",
                "--include", str(FIXTURES_DIR / "*.po"),
                "--exclude", str(FIXTURES_DIR / "malformed.po"),
                "--format", "text"
            ],
            capture_output=True,
            text=True
        )

        # Should process multiple files
        # Check that multiple files appear in output
        po_files = [".po:" in line for line in result.stdout.split('\n')]
        assert any(po_files)

    def test_lint_exit_code_clean(self):
        """Test exit code for clean file (no issues)."""
        # Create a clean PO file
        with NamedTemporaryFile(mode='w', delete=False, suffix='.po') as f:
            f.write('msgid ""\nmsgstr ""\n\n')
            f.write('#: file.py:1\nmsgid "Test"\nmsgstr "Test"\n')
            clean_file = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-m", "polyglott", "lint", clean_file],
                capture_output=True,
                text=True
            )

            # Should return 0 for clean file
            assert result.returncode == 0
        finally:
            Path(clean_file).unlink()

    def test_lint_exit_code_errors(self):
        """Test exit code 1 for errors."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "lint",
                str(FIXTURES_DIR / "format_issues.po")
            ],
            capture_output=True,
            text=True
        )

        # format_issues.po has format errors
        assert result.returncode == 1

    def test_lint_exit_code_warnings(self):
        """Test exit code 2 for warnings only."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "lint",
                str(FIXTURES_DIR / "term_issues.po"),
                "--glossary", str(FIXTURES_DIR / "glossary.yaml"),
                "--check", "term_mismatch"  # Only check term_mismatch (warnings)
            ],
            capture_output=True,
            text=True
        )

        # term_issues.po has term warnings but no errors
        assert result.returncode == 2

    def test_lint_to_file(self):
        """Test linting with output to file."""
        with NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            output_file = f.name

        try:
            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "lint",
                    str(FIXTURES_DIR / "format_issues.po"),
                    "-o", output_file
                ],
                capture_output=True,
                text=True
            )

            # Read and verify CSV
            with open(output_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) > 0
            assert "severity" in rows[0]
            assert "check" in rows[0]
            assert "message" in rows[0]
        finally:
            Path(output_file).unlink()

    def test_lint_no_args_error(self):
        """Test error when no file or --include specified."""
        result = subprocess.run(
            [sys.executable, "-m", "polyglott", "lint"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 1
        assert "Must specify either FILE or --include" in result.stderr

    def test_lint_missing_file(self):
        """Test error handling for missing file."""
        result = subprocess.run(
            [sys.executable, "-m", "polyglott", "lint", "nonexistent.po"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 1
        assert "not found" in result.stderr.lower()

    def test_scan_still_works(self):
        """Regression test: ensure scan subcommand still works."""
        result = subprocess.run(
            [sys.executable, "-m", "polyglott", "scan", str(FIXTURES_DIR / "simple.po")],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "Total entries: 4" in result.stderr
