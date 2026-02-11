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
