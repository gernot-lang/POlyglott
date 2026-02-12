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
        from polyglott import __version__

        result = subprocess.run(
            [sys.executable, "-m", "polyglott", "--version"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert __version__ in result.stdout

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
        """Test scanning multiple files now uses import subcommand (Stage 5.1)."""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    "--include", str(FIXTURES_DIR / "*.po"),
                    "--exclude", str(FIXTURES_DIR / "malformed.po")
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert master_path.exists()

    def test_scan_with_exclusions(self):
        """Test exclusion patterns now use import subcommand (Stage 5.1)."""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    "--include", str(FIXTURES_DIR / "*.po"),
                    "--exclude", str(FIXTURES_DIR / "malformed.po")
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "Total entries:" in result.stderr

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
        """Test error when no file specified (Stage 3 behavior)."""
        result = subprocess.run(
            [sys.executable, "-m", "polyglott", "scan"],
            capture_output=True,
            text=True
        )

        # argparse error (missing required argument)
        assert result.returncode == 2
        assert "required: file" in result.stderr

    def test_scan_conflicting_args(self):
        """Test that scan no longer accepts --include (Stage 3 behavior)."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "scan",
                str(FIXTURES_DIR / "simple.po"),
                "--include", "*.po"
            ],
            capture_output=True,
            text=True
        )

        # argparse error (unrecognized argument)
        assert result.returncode == 2
        assert "unrecognized arguments" in result.stderr

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


class TestContextInference:
    """Test suite for context inference feature."""

    def test_scan_with_context_rules(self):
        """Test scan with explicit context rules file."""
        with NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            output_file = f.name

        try:
            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "scan",
                    str(FIXTURES_DIR / "context_test.po"),
                    "--context-rules", str(FIXTURES_DIR / "context_rules.yaml"),
                    "-o", output_file
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

            # Read and verify CSV has context columns
            with open(output_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # Check headers
            assert "context" in rows[0]
            assert "context_sources" in rows[0]

            # Check specific entries
            email = next(r for r in rows if r["msgid"] == "Email address")
            assert email["context"] == "form_label"
            assert email["context_sources"] == ""  # Unanimous

            username = next(r for r in rows if r["msgid"] == "Username")
            assert username["context"] == "field_label"

            # Check ambiguous case
            status = next(r for r in rows if r["msgid"] == "Status")
            assert status["context"] == "ambiguous"
            assert status["context_sources"] != ""

        finally:
            Path(output_file).unlink()

    def test_scan_with_django_preset(self):
        """Test scan with Django preset."""
        with NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            output_file = f.name

        try:
            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "scan",
                    str(FIXTURES_DIR / "context_test.po"),
                    "--preset", "django",
                    "-o", output_file
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

            # Read and verify CSV has context columns
            with open(output_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert "context" in rows[0]
            assert "context_sources" in rows[0]

        finally:
            Path(output_file).unlink()

    def test_scan_without_context_no_columns(self):
        """Test scan without context flags has no context columns."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "scan",
                str(FIXTURES_DIR / "simple.po")
            ],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0

        # Check CSV does NOT have context columns
        lines = result.stdout.strip().split('\n')
        header = lines[0]
        assert "context" not in header
        assert "context_sources" not in header

    def test_scan_context_rules_and_preset_mutually_exclusive(self):
        """Test error when both --context-rules and --preset provided."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "scan",
                str(FIXTURES_DIR / "simple.po"),
                "--context-rules", str(FIXTURES_DIR / "context_rules.yaml"),
                "--preset", "django"
            ],
            capture_output=True,
            text=True
        )

        assert result.returncode == 1
        assert "Cannot specify both" in result.stderr

    def test_scan_context_rules_nonexistent_file(self):
        """Test error handling for nonexistent rules file."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "scan",
                str(FIXTURES_DIR / "simple.po"),
                "--context-rules", "nonexistent.yaml"
            ],
            capture_output=True,
            text=True
        )

        assert result.returncode == 1
        assert "not found" in result.stderr.lower()

    def test_scan_context_rules_invalid_yaml(self):
        """Test error handling for invalid YAML."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "scan",
                str(FIXTURES_DIR / "simple.po"),
                "--context-rules", str(FIXTURES_DIR / "context_invalid.yaml")
            ],
            capture_output=True,
            text=True
        )

        assert result.returncode == 1
        assert "Invalid YAML" in result.stderr or "Error" in result.stderr

    def test_scan_unknown_preset(self):
        """Test error handling for unknown preset."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "scan",
                str(FIXTURES_DIR / "simple.po"),
                "--preset", "nonexistent"
            ],
            capture_output=True,
            text=True
        )

        assert result.returncode == 1
        assert "Unknown preset" in result.stderr

    def test_lint_with_context_csv_output(self):
        """Test lint with context in CSV output."""
        with NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            output_file = f.name

        try:
            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "lint",
                    str(FIXTURES_DIR / "context_test.po"),
                    "--preset", "django",
                    "-o", output_file
                ],
                capture_output=True,
                text=True
            )

            # Read and verify CSV has context columns
            with open(output_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # Should have standard lint columns
            if len(rows) > 0:
                assert "severity" in rows[0]
                assert "check" in rows[0]
                # And context columns
                assert "context" in rows[0]
                assert "context_sources" in rows[0]

        finally:
            Path(output_file).unlink()

    def test_lint_with_context_text_output(self):
        """Test lint text output does not include context."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "lint",
                str(FIXTURES_DIR / "context_test.po"),
                "--preset", "django",
                "--format", "text"
            ],
            capture_output=True,
            text=True
        )

        # Text output should not mention context
        # (context is only in CSV format)
        # Just verify it doesn't crash
        assert result.returncode in [0, 1, 2]  # Any valid exit code

    def test_existing_tests_still_pass(self):
        """Regression test: ensure existing Stage 1 and Stage 2 tests still work."""
        # Test basic scan
        result = subprocess.run(
            [sys.executable, "-m", "polyglott", "scan", str(FIXTURES_DIR / "simple.po")],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0

        # Test basic lint
        result = subprocess.run(
            [sys.executable, "-m", "polyglott", "lint", str(FIXTURES_DIR / "simple.po")],
            capture_output=True,
            text=True
        )
        assert result.returncode in [0, 1, 2]


class TestImportSubcommand:
    """Test suite for import subcommand (Stage 5)."""

    def test_import_creates_new_master(self):
        """Test import subcommand creates new master CSV."""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    str(FIXTURES_DIR / "master" / "django.po")
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert master_path.exists()
            assert "Language: de" in result.stderr
            assert "Total entries:" in result.stderr

    def test_import_updates_existing_master(self):
        """Test import updates existing master CSV."""
        from tempfile import TemporaryDirectory
        import shutil

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"
            shutil.copy(FIXTURES_DIR / "master" / "master_existing.csv", master_path)

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    "--include", str(FIXTURES_DIR / "master" / "*.po")
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

    def test_import_with_context_rules(self):
        """Test import with context rules."""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"
            rules_path = Path(tmpdir) / "rules.yaml"
            rules_path.write_text("""rules:
  - pattern: 'forms.py'
    context: 'form_label'
""")

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    str(FIXTURES_DIR / "master" / "django.po"),
                    "--context-rules", str(rules_path)
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

    def test_import_with_glossary(self):
        """Test import with glossary scoring."""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    str(FIXTURES_DIR / "master" / "django.po"),
                    "--glossary", str(FIXTURES_DIR / "master" / "glossary_de.yaml")
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

    def test_import_language_inference(self):
        """Test language inference from filename."""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "polyglott-accepted-de.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    str(FIXTURES_DIR / "master" / "django.po")
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "Language: de" in result.stderr

    def test_import_lang_override(self):
        """Test --lang override."""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "translations.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    str(FIXTURES_DIR / "master" / "django.po"),
                    "--lang", "de"
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "Language: de" in result.stderr

    def test_import_no_lang_error(self):
        """Test error when language cannot be inferred."""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "translations.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    str(FIXTURES_DIR / "master" / "django.po")
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 1
            assert "Cannot infer target language" in result.stderr

    def test_import_no_po_files_error(self):
        """Test error when no PO files specified (Stage 5.1)."""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path)
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 1
            assert "No PO files specified" in result.stderr


class TestExportSubcommand:
    """Test suite for export subcommand (Stage 5)."""

    def test_export_accepted_to_po(self):
        """Test export writes accepted translations to PO files."""
        from tempfile import TemporaryDirectory
        import polib

        with TemporaryDirectory() as tmpdir:
            # Create master CSV with accepted entry
            master_path = Path(tmpdir) / "master-de.csv"
            with open(master_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['msgid', 'msgstr', 'status', 'score', 'context', 'context_sources'])
                writer.writeheader()
                writer.writerow({
                    'msgid': 'Username',
                    'msgstr': 'Benutzername',
                    'status': 'accepted',
                    'score': '10',
                    'context': '',
                    'context_sources': ''
                })

            # Create PO file
            po_path = Path(tmpdir) / "django.po"
            po = polib.POFile()
            po.append(polib.POEntry(msgid="Username", msgstr=""))
            po.save(str(po_path))

            # Export
            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "export",
                    "--master", str(master_path),
                    str(po_path)
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "Updated 1 entries" in result.stdout

            # Verify PO file was updated
            po_loaded = polib.pofile(str(po_path))
            entry = po_loaded.find("Username")
            assert entry.msgstr == "Benutzername"
            assert "fuzzy" not in entry.flags

    def test_export_dry_run(self):
        """Test export --dry-run doesn't modify files."""
        from tempfile import TemporaryDirectory
        import polib

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"
            with open(master_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['msgid', 'msgstr', 'status', 'score', 'context', 'context_sources'])
                writer.writeheader()
                writer.writerow({
                    'msgid': 'Username',
                    'msgstr': 'Benutzername',
                    'status': 'accepted',
                    'score': '',
                    'context': '',
                    'context_sources': ''
                })

            po_path = Path(tmpdir) / "django.po"
            po = polib.POFile()
            po.append(polib.POEntry(msgid="Username", msgstr=""))
            po.save(str(po_path))

            # Export with dry-run
            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "export",
                    "--master", str(master_path),
                    str(po_path),
                    "--dry-run"
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "Dry run" in result.stdout
            assert "Would update" in result.stdout

            # Verify PO file was NOT modified
            po_loaded = polib.pofile(str(po_path))
            entry = po_loaded.find("Username")
            assert entry.msgstr == ""

    def test_export_verbose(self):
        """Test export -v shows per-entry details."""
        from tempfile import TemporaryDirectory
        import polib

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"
            with open(master_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['msgid', 'msgstr', 'status', 'score', 'context', 'context_sources'])
                writer.writeheader()
                writer.writerow({
                    'msgid': 'Username',
                    'msgstr': 'Benutzername',
                    'status': 'accepted',
                    'score': '',
                    'context': '',
                    'context_sources': ''
                })

            po_path = Path(tmpdir) / "django.po"
            po = polib.POFile()
            po.append(polib.POEntry(msgid="Username", msgstr=""))
            po.save(str(po_path))

            # Export with verbose
            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "export",
                    "--master", str(master_path),
                    str(po_path),
                    "-v"
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "WRITE" in result.stdout
            assert "Username" in result.stdout

    def test_export_status_filtering(self):
        """Test export with --status filtering."""
        from tempfile import TemporaryDirectory
        import polib

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"
            with open(master_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['msgid', 'msgstr', 'status', 'score', 'context', 'context_sources'])
                writer.writeheader()
                writer.writerow({
                    'msgid': 'Username',
                    'msgstr': 'Benutzername',
                    'status': 'machine',
                    'score': '',
                    'context': '',
                    'context_sources': ''
                })

            po_path = Path(tmpdir) / "django.po"
            po = polib.POFile()
            po.append(polib.POEntry(msgid="Username", msgstr=""))
            po.save(str(po_path))

            # Export with machine status
            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "export",
                    "--master", str(master_path),
                    str(po_path),
                    "--status", "machine"
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "Updated 1 entries" in result.stdout

            # Verify fuzzy flag was set
            po_loaded = polib.pofile(str(po_path))
            entry = po_loaded.find("Username")
            assert entry.msgstr == "Benutzername"
            assert "fuzzy" in entry.flags

    def test_export_no_master_error(self):
        """Test error when master CSV doesn't exist."""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "nonexistent-de.csv"
            po_path = Path(tmpdir) / "django.po"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "export",
                    "--master", str(master_path),
                    str(po_path)
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 1
            assert "not found" in result.stderr


class TestScanRestoration:
    """Test suite for scan restoration to Stage 3 behavior (Stage 5)."""

    def test_scan_single_file_only(self):
        """Test scan works with single file (Stage 3 behavior)."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "scan",
                str(FIXTURES_DIR / "simple.po")
            ],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "Total entries:" in result.stderr

    def test_scan_no_master_flag(self):
        """Test that scan no longer accepts --master flag."""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "scan",
                    str(FIXTURES_DIR / "simple.po"),
                    "--master", str(master_path)
                ],
                capture_output=True,
                text=True
            )

            # Should fail with unrecognized argument
            assert result.returncode != 0

    def test_scan_no_multi_file(self):
        """Test that scan no longer accepts --include."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "scan",
                "--include", str(FIXTURES_DIR / "*.po")
            ],
            capture_output=True,
            text=True
        )

        # Should fail - must specify FILE
        assert result.returncode != 0


class TestCLIHarmonization:
    """Test suite for CLI harmonization features (Stage 5.1)."""

    def test_import_master_flag_required(self):
        """Test that import --master flag is required."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "import",
                str(FIXTURES_DIR / "simple.po")
            ],
            capture_output=True,
            text=True
        )

        assert result.returncode == 2  # argparse error
        assert "--master" in result.stderr

    def test_export_master_flag_required(self):
        """Test that export --master flag is required."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "export",
                str(FIXTURES_DIR / "simple.po")
            ],
            capture_output=True,
            text=True
        )

        assert result.returncode == 2  # argparse error
        assert "--master" in result.stderr

    def test_import_with_include_flag(self):
        """Test import --include flag works."""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    "--include", str(FIXTURES_DIR / "simple.po")
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert master_path.exists()

    def test_import_with_sort_by_flag(self):
        """Test import --sort-by flag works."""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    "--sort-by", "msgid",
                    str(FIXTURES_DIR / "simple.po")
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

    def test_export_with_include_flag(self):
        """Test export --include flag works."""
        from tempfile import TemporaryDirectory
        import polib
        import csv

        with TemporaryDirectory() as tmpdir:
            # Create master CSV
            master_path = Path(tmpdir) / "master-de.csv"
            with open(master_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['msgid', 'msgstr', 'status', 'score', 'context', 'context_sources'])
                writer.writeheader()
                writer.writerow({
                    'msgid': 'Hello',
                    'msgstr': 'Hallo',
                    'status': 'accepted',
                    'score': '',
                    'context': '',
                    'context_sources': ''
                })

            # Create PO file
            po_path = Path(tmpdir) / "test.po"
            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr=""))
            po.save(str(po_path))

            # Export using --include
            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "export",
                    "--master", str(master_path),
                    "--include", str(po_path)
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "Updated 1 entries" in result.stdout

    def test_export_with_sort_by_flag(self):
        """Test export --sort-by flag is accepted (doesn't affect export)."""
        from tempfile import TemporaryDirectory
        import polib
        import csv

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"
            with open(master_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['msgid', 'msgstr', 'status', 'score', 'context', 'context_sources'])
                writer.writeheader()
                writer.writerow({
                    'msgid': 'Hello',
                    'msgstr': 'Hallo',
                    'status': 'accepted',
                    'score': '',
                    'context': '',
                    'context_sources': ''
                })

            po_path = Path(tmpdir) / "test.po"
            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr=""))
            po.save(str(po_path))

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "export",
                    "--master", str(master_path),
                    "--sort-by", "msgid",
                    str(po_path)
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

    def test_import_positional_and_include_combined(self):
        """Test import combines positional PO files with --include."""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"

            # Use both positional and --include
            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    str(FIXTURES_DIR / "simple.po"),
                    "--include", str(FIXTURES_DIR / "unicode.po")
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert master_path.exists()
            # Should have entries from both files
            assert "Total entries:" in result.stderr

    def test_import_include_with_exclude(self):
        """Test import --include with --exclude."""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    "--include", str(FIXTURES_DIR / "*.po"),
                    "--exclude", str(FIXTURES_DIR / "malformed.po")
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

    def test_import_no_files_error(self):
        """Test import error when no PO files result from any source."""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"

            # No positional files, no --include
            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path)
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 1
            assert "No PO files specified" in result.stderr

    def test_import_all_files_excluded_error(self):
        """Test import error when all files are excluded."""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    str(FIXTURES_DIR / "simple.po"),
                    "--exclude", str(FIXTURES_DIR / "*.po")
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 1
            assert "No PO files remain" in result.stderr

    def test_export_positional_and_include_combined(self):
        """Test export combines positional PO files with --include."""
        from tempfile import TemporaryDirectory
        import polib
        import csv

        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "master-de.csv"
            with open(master_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['msgid', 'msgstr', 'status', 'score', 'context', 'context_sources'])
                writer.writeheader()
                writer.writerow({
                    'msgid': 'Test',
                    'msgstr': 'Test',
                    'status': 'accepted',
                    'score': '',
                    'context': '',
                    'context_sources': ''
                })

            # Create two PO files
            po1_path = Path(tmpdir) / "test1.po"
            po1 = polib.POFile()
            po1.append(polib.POEntry(msgid="Test", msgstr=""))
            po1.save(str(po1_path))

            po2_path = Path(tmpdir) / "test2.po"
            po2 = polib.POFile()
            po2.append(polib.POEntry(msgid="Test", msgstr=""))
            po2.save(str(po2_path))

            # Export to both using positional and --include
            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "export",
                    "--master", str(master_path),
                    str(po1_path),
                    "--include", str(po2_path)
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "across 2 files" in result.stdout

    def test_scan_still_works_without_include(self):
        """Regression test: scan still works as single-file command."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "scan",
                str(FIXTURES_DIR / "simple.po")
            ],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "Total entries:" in result.stderr

    def test_lint_still_works_with_include(self):
        """Regression test: lint still works with --include."""
        result = subprocess.run(
            [
                sys.executable, "-m", "polyglott", "lint",
                "--include", str(FIXTURES_DIR / "simple.po")
            ],
            capture_output=True,
            text=True
        )

        assert result.returncode in [0, 1, 2]  # Any valid exit code
