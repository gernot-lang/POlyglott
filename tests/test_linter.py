"""Tests for the linter module."""

import pytest

from polyglott.linter import (
    Glossary,
    Severity,
    Violation,
    check_untranslated,
    check_fuzzy,
    check_obsolete,
    check_format_mismatch,
    check_term_mismatch,
    registry,
    run_checks,
    _extract_placeholders,
)
from polyglott.parser import POEntryData, POParser


@pytest.fixture
def simple_entry():
    """Create a simple translated entry."""
    return POEntryData(
        msgid="Hello",
        msgstr="Bonjour",
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


@pytest.fixture
def untranslated_entry():
    """Create an untranslated entry."""
    return POEntryData(
        msgid="Untranslated",
        msgstr="",
        msgctxt=None,
        extracted_comments="",
        translator_comments="",
        references="file.py:20",
        fuzzy=False,
        obsolete=False,
        is_plural=False,
        plural_index=None,
        source_file="test.po"
    )


@pytest.fixture
def fuzzy_entry():
    """Create a fuzzy entry."""
    return POEntryData(
        msgid="Fuzzy",
        msgstr="Flou",
        msgctxt=None,
        extracted_comments="",
        translator_comments="",
        references="file.py:30",
        fuzzy=True,
        obsolete=False,
        is_plural=False,
        plural_index=None,
        source_file="test.po"
    )


@pytest.fixture
def obsolete_entry():
    """Create an obsolete entry."""
    return POEntryData(
        msgid="Obsolete",
        msgstr="Obsolète",
        msgctxt=None,
        extracted_comments="",
        translator_comments="",
        references="file.py:40",
        fuzzy=False,
        obsolete=True,
        is_plural=False,
        plural_index=None,
        source_file="test.po"
    )


@pytest.fixture
def format_mismatch_entry():
    """Create an entry with format mismatch."""
    return POEntryData(
        msgid="Hello %(name)s",
        msgstr="Bonjour",
        msgctxt=None,
        extracted_comments="",
        translator_comments="",
        references="file.py:50",
        fuzzy=False,
        obsolete=False,
        is_plural=False,
        plural_index=None,
        source_file="test.po"
    )


class TestBuiltinChecks:
    """Test built-in check functions."""

    def test_check_untranslated(self, simple_entry, untranslated_entry):
        """Test untranslated check."""
        # Should not flag translated entry
        assert check_untranslated(simple_entry) is None

        # Should flag untranslated entry
        violation = check_untranslated(untranslated_entry)
        assert violation is not None
        assert violation.severity == Severity.ERROR
        assert violation.check_name == "untranslated"

    def test_check_fuzzy(self, simple_entry, fuzzy_entry):
        """Test fuzzy check."""
        # Should not flag non-fuzzy entry
        assert check_fuzzy(simple_entry) is None

        # Should flag fuzzy entry
        violation = check_fuzzy(fuzzy_entry)
        assert violation is not None
        assert violation.severity == Severity.WARNING
        assert violation.check_name == "fuzzy"

    def test_check_obsolete(self, simple_entry, obsolete_entry):
        """Test obsolete check."""
        # Should not flag non-obsolete entry
        assert check_obsolete(simple_entry) is None

        # Should flag obsolete entry
        violation = check_obsolete(obsolete_entry)
        assert violation is not None
        assert violation.severity == Severity.INFO
        assert violation.check_name == "obsolete"

    def test_check_format_mismatch(self, simple_entry, format_mismatch_entry, untranslated_entry):
        """Test format mismatch check."""
        # Should not flag entry without format strings
        assert check_format_mismatch(simple_entry) is None

        # Should not flag untranslated entry
        assert check_format_mismatch(untranslated_entry) is None

        # Should flag format mismatch
        violation = check_format_mismatch(format_mismatch_entry)
        assert violation is not None
        assert violation.severity == Severity.ERROR
        assert violation.check_name == "format_mismatch"
        assert "missing" in violation.message

    def test_format_mismatch_extra_placeholder(self):
        """Test format mismatch with extra placeholder."""
        entry = POEntryData(
            msgid="Hello",
            msgstr="Bonjour %(extra)s",
            msgctxt=None,
            extracted_comments="",
            translator_comments="",
            references="file.py:60",
            fuzzy=False,
            obsolete=False,
            is_plural=False,
            plural_index=None,
            source_file="test.po"
        )
        violation = check_format_mismatch(entry)
        assert violation is not None
        assert "extra" in violation.message

    def test_format_mismatch_brace_style(self):
        """Test format mismatch with brace-style placeholders."""
        entry = POEntryData(
            msgid="Hello {name}",
            msgstr="Bonjour",
            msgctxt=None,
            extracted_comments="",
            translator_comments="",
            references="file.py:70",
            fuzzy=False,
            obsolete=False,
            is_plural=False,
            plural_index=None,
            source_file="test.po"
        )
        violation = check_format_mismatch(entry)
        assert violation is not None
        assert "missing" in violation.message


class TestExtractPlaceholders:
    """Test placeholder extraction."""

    def test_extract_percent_style(self):
        """Test extracting percent-style placeholders."""
        text = "Hello %(name)s, you have %(count)d messages"
        placeholders = _extract_placeholders(text)
        assert placeholders == {"%(name)s", "%(count)d"}

    def test_extract_brace_style(self):
        """Test extracting brace-style placeholders."""
        text = "Hello {0}, you have {count} messages"
        placeholders = _extract_placeholders(text)
        assert placeholders == {"{0}", "{count}"}

    def test_extract_mixed_style(self):
        """Test extracting mixed-style placeholders."""
        text = "Hello %(name)s and {0}"
        placeholders = _extract_placeholders(text)
        assert placeholders == {"%(name)s", "{0}"}

    def test_extract_no_placeholders(self):
        """Test text with no placeholders."""
        text = "Hello world"
        placeholders = _extract_placeholders(text)
        assert placeholders == set()


class TestGlossary:
    """Test glossary loading and validation."""

    def test_load_valid_glossary(self, tmp_path):
        """Test loading a valid glossary."""
        glossary_file = tmp_path / "glossary.yaml"
        glossary_file.write_text("language: de\nterms:\n  file: Datei\n  folder: Ordner\n")

        glossary = Glossary(str(glossary_file))
        assert glossary.language == "de"
        assert glossary.terms == {"file": "Datei", "folder": "Ordner"}

    def test_load_nonexistent_glossary(self):
        """Test loading a nonexistent glossary."""
        with pytest.raises(FileNotFoundError):
            Glossary("/nonexistent/glossary.yaml")

    def test_load_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML."""
        glossary_file = tmp_path / "invalid.yaml"
        glossary_file.write_text("invalid: [yaml structure")

        with pytest.raises(ValueError, match="Invalid YAML"):
            Glossary(str(glossary_file))

    def test_load_no_terms_section(self, tmp_path):
        """Test loading glossary without terms section."""
        glossary_file = tmp_path / "no_terms.yaml"
        glossary_file.write_text("language: de\n")

        with pytest.raises(ValueError, match="must have a 'terms' section"):
            Glossary(str(glossary_file))

    def test_load_empty_terms(self, tmp_path):
        """Test loading glossary with empty terms."""
        glossary_file = tmp_path / "empty_terms.yaml"
        glossary_file.write_text("language: de\nterms: {}\n")

        with pytest.raises(ValueError, match="'terms' section is empty"):
            Glossary(str(glossary_file))

    def test_load_terms_as_list(self, tmp_path):
        """Test loading glossary with terms as list instead of dict.

        This reproduces the bug: 'list' object has no attribute 'items'
        """
        glossary_file = tmp_path / "list_terms.yaml"
        glossary_file.write_text("""language: de
terms:
  - source: file
    target: Datei
  - source: folder
    target: Ordner
""")

        with pytest.raises(ValueError, match="must be a dictionary"):
            Glossary(str(glossary_file))

    def test_source_term_case_insensitive_key(self, tmp_path):
        """Test that glossary keys are normalized to lowercase.

        Glossary: 'File: Datei' (capital F)
        Source: 'open the file' (lowercase f)
        Should match!
        """
        glossary_file = tmp_path / "glossary.yaml"
        glossary_file.write_text("language: de\nterms:\n  File: Datei\n")

        glossary = Glossary(str(glossary_file))

        # Lowercase in source should match uppercase glossary key
        error = glossary.check_term("Open the file", "Öffnen Sie die Datei")
        assert error is None

    def test_source_term_case_insensitive_matching(self, tmp_path):
        """Test case-insensitive matching for source terms."""
        glossary_file = tmp_path / "glossary.yaml"
        glossary_file.write_text("language: de\nterms:\n  pipeline: Pipeline\n")

        glossary = Glossary(str(glossary_file))

        # All these should match
        test_cases = [
            ("pipeline", "Pipeline"),
            ("Pipeline", "Pipeline"),
            ("PIPELINE", "Pipeline"),
            ("The pipeline is", "Die Pipeline ist"),
            ("The Pipeline is", "Die Pipeline ist"),
            ("THE PIPELINE IS", "Die Pipeline ist"),
        ]

        for msgid, msgstr in test_cases:
            error = glossary.check_term(msgid, msgstr)
            assert error is None, f"Failed for msgid='{msgid}'"

    def test_translation_case_insensitive_matching(self, tmp_path):
        """Test case-insensitive matching for translations."""
        glossary_file = tmp_path / "glossary.yaml"
        glossary_file.write_text("language: de\nterms:\n  pipeline: Pipeline\n")

        glossary = Glossary(str(glossary_file))

        # All these translations should match (case-insensitive)
        test_cases = [
            ("pipeline", "pipeline"),  # lowercase
            ("pipeline", "Pipeline"),  # exact match
            ("pipeline", "PIPELINE"),  # uppercase
            ("pipeline", "Die pipeline ist"),  # in sentence
            ("pipeline", "Die Pipeline ist"),  # in sentence, capitalized
        ]

        for msgid, msgstr in test_cases:
            error = glossary.check_term(msgid, msgstr)
            assert error is None, f"Failed for msgstr='{msgstr}'"

    def test_mixed_case_glossary_keys(self, tmp_path):
        """Test that mixed-case glossary keys are normalized."""
        glossary_file = tmp_path / "glossary.yaml"
        glossary_file.write_text("""language: de
terms:
  File: Datei
  Pipeline: Pipeline
  NODE: Knoten
  eDge: Kante
""")

        glossary = Glossary(str(glossary_file))

        # All lowercase source terms should match
        assert glossary.check_term("Open the file", "Öffnen Sie die Datei") is None
        assert glossary.check_term("pipeline status", "Pipeline-Status") is None
        assert glossary.check_term("graph node", "Graph-Knoten") is None
        assert glossary.check_term("edge weight", "Kante Gewicht") is None

    def test_check_term_match(self, tmp_path):
        """Test glossary term checking with correct term."""
        glossary_file = tmp_path / "glossary.yaml"
        glossary_file.write_text("language: de\nterms:\n  file: Datei\n")

        glossary = Glossary(str(glossary_file))
        error = glossary.check_term("Open the file", "Öffnen Sie die Datei")
        assert error is None

    def test_check_term_mismatch(self, tmp_path):
        """Test glossary term checking with incorrect term."""
        glossary_file = tmp_path / "glossary.yaml"
        glossary_file.write_text("language: de\nterms:\n  file: Datei\n")

        glossary = Glossary(str(glossary_file))
        error = glossary.check_term("Open the file", "Öffnen Sie die Akte")
        assert error is not None
        assert "Datei" in error
        assert "file" in error

    def test_check_term_word_boundary(self, tmp_path):
        """Test glossary respects word boundaries."""
        glossary_file = tmp_path / "glossary.yaml"
        glossary_file.write_text("language: de\nterms:\n  file: Datei\n")

        glossary = Glossary(str(glossary_file))
        # "profile" should not match "file"
        error = glossary.check_term("View user profile", "Benutzerprofil anzeigen")
        assert error is None

    def test_check_term_case_insensitive_source(self, tmp_path):
        """Test glossary source matching is case-insensitive."""
        glossary_file = tmp_path / "glossary.yaml"
        glossary_file.write_text("language: de\nterms:\n  file: Datei\n")

        glossary = Glossary(str(glossary_file))
        # "File" (capital F) should match "file"
        error = glossary.check_term("Open the File", "Öffnen Sie die Datei")
        assert error is None

    def test_check_term_untranslated(self, tmp_path):
        """Test glossary skips untranslated entries."""
        glossary_file = tmp_path / "glossary.yaml"
        glossary_file.write_text("language: de\nterms:\n  file: Datei\n")

        glossary = Glossary(str(glossary_file))
        error = glossary.check_term("Open the file", "")
        assert error is None


class TestTermMismatchCheck:
    """Test term mismatch check function."""

    def test_check_term_mismatch_no_glossary(self, simple_entry):
        """Test term mismatch check without glossary."""
        violation = check_term_mismatch(simple_entry, glossary=None)
        assert violation is None

    def test_check_term_mismatch_with_glossary(self, tmp_path):
        """Test term mismatch check with glossary."""
        glossary_file = tmp_path / "glossary.yaml"
        glossary_file.write_text("language: de\nterms:\n  file: Datei\n")

        glossary = Glossary(str(glossary_file))

        # Entry with correct term
        entry = POEntryData(
            msgid="Open the file",
            msgstr="Öffnen Sie die Datei",
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
        violation = check_term_mismatch(entry, glossary)
        assert violation is None

        # Entry with incorrect term
        entry_bad = POEntryData(
            msgid="Open the file",
            msgstr="Öffnen Sie die Akte",
            msgctxt=None,
            extracted_comments="",
            translator_comments="",
            references="file.py:20",
            fuzzy=False,
            obsolete=False,
            is_plural=False,
            plural_index=None,
            source_file="test.po"
        )
        violation = check_term_mismatch(entry_bad, glossary)
        assert violation is not None
        assert violation.severity == Severity.WARNING
        assert violation.check_name == "term_mismatch"


class TestCheckRegistry:
    """Test check registry."""

    def test_registry_has_checks(self):
        """Test registry contains expected checks."""
        checks = registry.get_all_checks()
        assert "untranslated" in checks
        assert "fuzzy" in checks
        assert "obsolete" in checks
        assert "format_mismatch" in checks
        assert "term_mismatch" in checks

    def test_get_active_checks_no_filter(self):
        """Test getting all checks without filters."""
        checks = registry.get_active_checks()
        assert len(checks) >= 5  # At least the 5 built-in checks

    def test_get_active_checks_include(self):
        """Test filtering with include list."""
        checks = registry.get_active_checks(include=["untranslated", "fuzzy"])
        assert len(checks) == 2
        assert "untranslated" in checks
        assert "fuzzy" in checks
        assert "obsolete" not in checks

    def test_get_active_checks_exclude(self):
        """Test filtering with exclude list."""
        checks = registry.get_active_checks(exclude=["obsolete", "term_mismatch"])
        assert "obsolete" not in checks
        assert "term_mismatch" not in checks
        assert "untranslated" in checks


class TestRunChecks:
    """Test running checks on entries."""

    def test_run_checks_no_violations(self, simple_entry):
        """Test running checks on clean entry."""
        violations = run_checks([simple_entry])
        assert len(violations) == 0

    def test_run_checks_untranslated(self, untranslated_entry):
        """Test running checks on untranslated entry."""
        violations = run_checks([untranslated_entry])
        assert len(violations) >= 1
        assert any(v.check_name == "untranslated" for v in violations)

    def test_run_checks_multiple_violations(self, untranslated_entry, fuzzy_entry):
        """Test running checks on multiple entries."""
        violations = run_checks([untranslated_entry, fuzzy_entry])
        assert len(violations) >= 2
        check_names = {v.check_name for v in violations}
        assert "untranslated" in check_names
        assert "fuzzy" in check_names

    def test_run_checks_with_include_filter(self, untranslated_entry, fuzzy_entry):
        """Test running checks with include filter."""
        violations = run_checks(
            [untranslated_entry, fuzzy_entry],
            include_checks=["untranslated"]
        )
        assert all(v.check_name == "untranslated" for v in violations)

    def test_run_checks_with_exclude_filter(self, untranslated_entry, fuzzy_entry):
        """Test running checks with exclude filter."""
        violations = run_checks(
            [untranslated_entry, fuzzy_entry],
            exclude_checks=["untranslated"]
        )
        assert all(v.check_name != "untranslated" for v in violations)


class TestIntegrationWithParser:
    """Test linter integration with parser."""

    def test_lint_format_issues_po(self):
        """Test linting format_issues.po fixture."""
        parser = POParser("tests/fixtures/format_issues.po")
        entries = parser.parse()
        violations = run_checks(entries, include_checks=["format_mismatch"])

        # Should find format mismatches
        assert len(violations) > 0
        assert all(v.check_name == "format_mismatch" for v in violations)

    def test_lint_complex_po(self):
        """Test linting complex.po fixture."""
        parser = POParser("tests/fixtures/complex.po")
        entries = parser.parse()
        violations = run_checks(entries)

        # Should find violations (untranslated, fuzzy, obsolete)
        assert len(violations) > 0
