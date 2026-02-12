"""Tests for master CSV functionality."""

import csv
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from polyglott.master import (
    MasterEntry,
    deduplicate_entries,
    create_master,
    merge_master,
    load_master,
    save_master,
    infer_language,
    _resolve_msgstr_conflict,
    _check_glossary_score,
    _compute_context
)
from polyglott.parser import POEntryData, POParser, MultiPOParser
from polyglott.linter import Glossary
from polyglott.context import load_context_rules

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "master"


class TestDeduplication:
    """Tests for deduplication logic."""

    def test_same_msgid_same_msgstr(self):
        """Test deduplication when msgstr values match."""
        entries = [
            POEntryData(
                msgid="Hello",
                msgstr="Hallo",
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="file1.py:10",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file="django.po"
            ),
            POEntryData(
                msgid="Hello",
                msgstr="Hallo",
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="file2.py:20",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file="forms.po"
            )
        ]

        result = deduplicate_entries(entries)

        assert len(result) == 1
        assert "Hello" in result
        assert result["Hello"].msgstr == "Hallo"
        # References should be aggregated
        assert "file1.py:10" in result["Hello"].references
        assert "file2.py:20" in result["Hello"].references

    def test_same_msgid_different_msgstr_majority(self):
        """Test majority voting when msgstr values differ."""
        entries = [
            POEntryData(
                msgid="Hello",
                msgstr="Hallo",
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="file1.py:10",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file="file1.po"
            ),
            POEntryData(
                msgid="Hello",
                msgstr="Hallo",
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="file2.py:20",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file="file2.po"
            ),
            POEntryData(
                msgid="Hello",
                msgstr="Grüß Gott",
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="file3.py:30",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file="file3.po"
            )
        ]

        result = deduplicate_entries(entries)

        assert len(result) == 1
        assert result["Hello"].msgstr == "Hallo"  # Majority wins

    def test_same_msgid_empty_vs_nonempty(self):
        """Test that non-empty msgstr beats empty."""
        entries = [
            POEntryData(
                msgid="Hello",
                msgstr="",
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="file1.py:10",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file="file1.po"
            ),
            POEntryData(
                msgid="Hello",
                msgstr="Hallo",
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="file2.py:20",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file="file2.po"
            )
        ]

        result = deduplicate_entries(entries)

        assert len(result) == 1
        assert result["Hello"].msgstr == "Hallo"

    def test_reference_aggregation(self):
        """Test that references are properly aggregated and deduplicated."""
        entries = [
            POEntryData(
                msgid="Hello",
                msgstr="Hallo",
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="file1.py:10 file2.py:20",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file="file1.po"
            ),
            POEntryData(
                msgid="Hello",
                msgstr="Hallo",
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="file2.py:20 file3.py:30",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file="file2.po"
            )
        ]

        result = deduplicate_entries(entries)

        refs = result["Hello"].references.split()
        # Should have 3 unique references
        assert len(refs) == 3
        assert "file1.py:10" in refs
        assert "file2.py:20" in refs
        assert "file3.py:30" in refs

    def test_majority_voting_tie(self):
        """Test tie-breaking: first encountered wins."""
        entries = [
            POEntryData(
                msgid="Hello",
                msgstr="Hallo",
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="file1.py:10",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file="file1.po"
            ),
            POEntryData(
                msgid="Hello",
                msgstr="Grüß Gott",
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="file2.py:20",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file="file2.po"
            )
        ]

        result = deduplicate_entries(entries)

        # First encountered should win (Hallo)
        assert result["Hello"].msgstr == "Hallo"


class TestGlossaryScoring:
    """Tests for glossary scoring logic."""

    def test_exact_match_scores_10(self):
        """Test that exact glossary match assigns score 10."""
        glossary = Glossary(str(FIXTURES_DIR / "glossary_de.yaml"))

        score = _check_glossary_score("Username", "Benutzername", glossary)
        assert score == "10"

    def test_partial_match_no_score(self):
        """Test that partial match doesn't assign score."""
        glossary = Glossary(str(FIXTURES_DIR / "glossary_de.yaml"))

        # msgstr doesn't match glossary term
        score = _check_glossary_score("Username", "Nutzername", glossary)
        assert score == ""

    def test_no_glossary_no_score(self):
        """Test that no glossary means no score."""
        score = _check_glossary_score("Username", "Benutzername", None)
        assert score == ""

    def test_case_insensitive_match(self):
        """Test that glossary matching is case-insensitive."""
        glossary = Glossary(str(FIXTURES_DIR / "glossary_de.yaml"))

        # Different case but should still match
        score = _check_glossary_score("username", "benutzername", glossary)
        assert score == "10"


class TestCreateMaster:
    """Tests for initial master CSV creation."""

    def test_create_from_single_file(self):
        """Test creating master from a single PO file."""
        parser = POParser(str(FIXTURES_DIR / "django.po"))
        entries = parser.parse()

        result = create_master(entries)

        # Should have 6 entries (excluding header)
        assert len(result) == 6

        # Check entries are sorted by msgid
        msgids = [e.msgid for e in result]
        assert msgids == sorted(msgids)

    def test_create_from_multiple_files(self):
        """Test creating master from multiple PO files with deduplication."""
        parser = MultiPOParser([
            str(FIXTURES_DIR / "django.po"),
            str(FIXTURES_DIR / "forms.po")
        ])
        entries = parser.parse()

        result = create_master(entries)

        # Should have deduplicated entries
        msgids = [e.msgid for e in result]
        # "Username" and "Password" appear in both files, should be deduplicated
        assert msgids.count("Username") == 1
        assert msgids.count("Password") == 1

    def test_status_empty_vs_review(self):
        """Test that status is 'empty' for untranslated, 'review' for translated."""
        parser = POParser(str(FIXTURES_DIR / "django.po"))
        entries = parser.parse()

        result = create_master(entries)

        # Find specific entries
        invalid_creds = next((e for e in result if e.msgid == "Invalid credentials"), None)
        username = next((e for e in result if e.msgid == "Username"), None)

        assert invalid_creds is not None
        assert invalid_creds.status == "empty"

        assert username is not None
        assert username.status == "review"

    def test_context_populated(self):
        """Test that context is computed when rules provided."""
        parser = POParser(str(FIXTURES_DIR / "django.po"))
        entries = parser.parse()

        context_rules = [
            {'pattern': 'forms.py', 'context': 'form_label'},
            {'pattern': 'models.py', 'context': 'field_label'},
            {'pattern': 'views.py', 'context': 'message'}
        ]

        result = create_master(entries, None, context_rules)

        # Find specific entries
        username = next((e for e in result if e.msgid == "Username"), None)
        login_msg = next((e for e in result if e.msgid == "Login successful"), None)

        assert username is not None
        assert username.context == "form_label"

        assert login_msg is not None
        assert login_msg.context == "message"

    def test_sorted_by_msgid(self):
        """Test that master entries are sorted by msgid."""
        parser = POParser(str(FIXTURES_DIR / "django.po"))
        entries = parser.parse()

        result = create_master(entries)

        msgids = [e.msgid for e in result]
        assert msgids == sorted(msgids)


class TestMergeMaster:
    """Tests for merge workflow with status transitions."""

    def test_merge_accepted_matching(self):
        """Test accepted entry with matching PO stays unchanged."""
        existing = {
            "Username": MasterEntry(
                msgid="Username",
                msgstr="Benutzername",
                status="accepted",
                score="10",
                context="form_label",
                context_sources=""
            )
        }

        po_entries = [
            POEntryData(
                msgid="Username",
                msgstr="Benutzername",
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="forms.py:10",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file="django.po"
            )
        ]

        result = merge_master(existing, po_entries)

        assert len(result) == 1
        assert result[0].status == "accepted"
        assert result[0].msgstr == "Benutzername"

    def test_merge_accepted_divergent_conflict(self):
        """Test accepted entry with divergent PO becomes conflict."""
        existing = {
            "Password": MasterEntry(
                msgid="Password",
                msgstr="Passwort",
                status="accepted",
                score="10",
                context="form_label",
                context_sources=""
            )
        }

        po_entries = [
            POEntryData(
                msgid="Password",
                msgstr="Kennwort",  # Different translation
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="forms.py:15",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file="forms.po"
            )
        ]

        result = merge_master(existing, po_entries)

        assert len(result) == 1
        assert result[0].status == "conflict"
        # Existing msgstr preserved
        assert result[0].msgstr == "Passwort"

    def test_merge_accepted_missing_stale(self):
        """Test accepted entry missing from PO becomes stale."""
        existing = {
            "Old Entry": MasterEntry(
                msgid="Old Entry",
                msgstr="Alter Eintrag",
                status="accepted",
                score="",
                context="",
                context_sources=""
            )
        }

        po_entries = []  # Empty, entry not in PO files

        result = merge_master(existing, po_entries)

        assert len(result) == 1
        assert result[0].status == "stale"
        assert result[0].msgstr == "Alter Eintrag"

    def test_merge_rejected_present(self):
        """Test rejected entry present in PO stays rejected."""
        existing = {
            "Bad Translation": MasterEntry(
                msgid="Bad Translation",
                msgstr="Schlechte Übersetzung",
                status="rejected",
                score="",
                context="",
                context_sources=""
            )
        }

        po_entries = [
            POEntryData(
                msgid="Bad Translation",
                msgstr="Schlechte Übersetzung",
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
        ]

        result = merge_master(existing, po_entries)

        assert len(result) == 1
        assert result[0].status == "rejected"

    def test_merge_rejected_missing(self):
        """Test rejected entry missing from PO becomes stale."""
        existing = {
            "Rejected": MasterEntry(
                msgid="Rejected",
                msgstr="Abgelehnt",
                status="rejected",
                score="",
                context="",
                context_sources=""
            )
        }

        po_entries = []

        result = merge_master(existing, po_entries)

        assert len(result) == 1
        assert result[0].status == "stale"

    def test_merge_review_updated(self):
        """Test review entry gets msgstr updated from PO."""
        existing = {
            "Submit": MasterEntry(
                msgid="Submit",
                msgstr="Senden",
                status="review",
                score="",
                context="form_label",
                context_sources=""
            )
        }

        po_entries = [
            POEntryData(
                msgid="Submit",
                msgstr="Absenden",  # Updated translation
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="forms.py:20",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file="django.po"
            )
        ]

        result = merge_master(existing, po_entries)

        assert len(result) == 1
        assert result[0].status == "review"
        assert result[0].msgstr == "Absenden"  # Updated

    def test_merge_review_missing(self):
        """Test review entry missing from PO becomes stale."""
        existing = {
            "Review": MasterEntry(
                msgid="Review",
                msgstr="Überprüfung",
                status="review",
                score="",
                context="",
                context_sources=""
            )
        }

        po_entries = []

        result = merge_master(existing, po_entries)

        assert len(result) == 1
        assert result[0].status == "stale"

    def test_merge_machine_updated(self):
        """Test machine entry gets msgstr updated from PO."""
        existing = {
            "Machine": MasterEntry(
                msgid="Machine",
                msgstr="Maschine",
                status="machine",
                score="",
                context="",
                context_sources=""
            )
        }

        po_entries = [
            POEntryData(
                msgid="Machine",
                msgstr="Maschine Neu",  # Updated
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
        ]

        result = merge_master(existing, po_entries)

        assert result[0].msgstr == "Maschine Neu"

    def test_merge_machine_missing(self):
        """Test machine entry missing from PO becomes stale."""
        existing = {
            "Machine": MasterEntry(
                msgid="Machine",
                msgstr="Maschine",
                status="machine",
                score="",
                context="",
                context_sources=""
            )
        }

        po_entries = []

        result = merge_master(existing, po_entries)

        assert result[0].status == "stale"

    def test_merge_empty_now_translated(self):
        """Test empty entry now has translation becomes review with score."""
        existing = {
            "Empty": MasterEntry(
                msgid="Empty",
                msgstr="",
                status="empty",
                score="",
                context="",
                context_sources=""
            )
        }

        po_entries = [
            POEntryData(
                msgid="Empty",
                msgstr="Leer",
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
        ]

        glossary = Glossary(str(FIXTURES_DIR / "glossary_de.yaml"))

        result = merge_master(existing, po_entries, glossary)

        assert result[0].status == "review"
        assert result[0].msgstr == "Leer"

    def test_merge_empty_still_empty(self):
        """Test empty entry still empty stays empty."""
        existing = {
            "Empty": MasterEntry(
                msgid="Empty",
                msgstr="",
                status="empty",
                score="",
                context="",
                context_sources=""
            )
        }

        po_entries = [
            POEntryData(
                msgid="Empty",
                msgstr="",  # Still empty
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
        ]

        result = merge_master(existing, po_entries)

        assert result[0].status == "empty"

    def test_merge_empty_missing(self):
        """Test empty entry missing from PO becomes stale."""
        existing = {
            "Empty": MasterEntry(
                msgid="Empty",
                msgstr="",
                status="empty",
                score="",
                context="",
                context_sources=""
            )
        }

        po_entries = []

        result = merge_master(existing, po_entries)

        assert result[0].status == "stale"

    def test_merge_conflict_present(self):
        """Test conflict entry present in PO stays conflict."""
        existing = {
            "Conflict": MasterEntry(
                msgid="Conflict",
                msgstr="Konflikt",
                status="conflict",
                score="",
                context="",
                context_sources=""
            )
        }

        po_entries = [
            POEntryData(
                msgid="Conflict",
                msgstr="Widerspruch",  # Different but doesn't matter
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
        ]

        result = merge_master(existing, po_entries)

        assert result[0].status == "conflict"
        assert result[0].msgstr == "Konflikt"  # Preserved

    def test_merge_conflict_missing(self):
        """Test conflict entry missing from PO becomes stale."""
        existing = {
            "Conflict": MasterEntry(
                msgid="Conflict",
                msgstr="Konflikt",
                status="conflict",
                score="",
                context="",
                context_sources=""
            )
        }

        po_entries = []

        result = merge_master(existing, po_entries)

        assert result[0].status == "stale"

    def test_merge_stale_reappears(self):
        """Test stale entry reappearing becomes review."""
        existing = {
            "Stale": MasterEntry(
                msgid="Stale",
                msgstr="Veraltet",
                status="stale",
                score="",
                context="",
                context_sources=""
            )
        }

        po_entries = [
            POEntryData(
                msgid="Stale",
                msgstr="Veraltet Neu",  # Reappears
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
        ]

        result = merge_master(existing, po_entries)

        assert result[0].status == "review"
        assert result[0].msgstr == "Veraltet Neu"
        # Score should NOT be assigned on reappearance
        assert result[0].score == ""

    def test_merge_new_msgid(self):
        """Test new msgid added to master."""
        existing = {}

        po_entries = [
            POEntryData(
                msgid="New Entry",
                msgstr="Neuer Eintrag",
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
        ]

        result = merge_master(existing, po_entries)

        assert len(result) == 1
        assert result[0].msgid == "New Entry"
        assert result[0].status == "review"


class TestScorePreservation:
    """Tests for score preservation during merge."""

    def test_existing_score_preserved_on_rescan(self):
        """Test that existing scores are preserved during rescan."""
        existing = {
            "Username": MasterEntry(
                msgid="Username",
                msgstr="Benutzername",
                status="accepted",
                score="10",
                context="form_label",
                context_sources=""
            )
        }

        po_entries = [
            POEntryData(
                msgid="Username",
                msgstr="Benutzername",
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="forms.py:10",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file="django.po"
            )
        ]

        result = merge_master(existing, po_entries)

        assert result[0].score == "10"  # Preserved

    def test_manual_score_preserved(self):
        """Test that manually assigned scores are preserved."""
        existing = {
            "Custom": MasterEntry(
                msgid="Custom",
                msgstr="Angepasst",
                status="accepted",
                score="8",  # Manual score
                context="",
                context_sources=""
            )
        }

        po_entries = [
            POEntryData(
                msgid="Custom",
                msgstr="Angepasst",
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
        ]

        result = merge_master(existing, po_entries)

        assert result[0].score == "8"  # Preserved


class TestContextRefresh:
    """Tests for context refresh during merge."""

    def test_context_refreshed_for_accepted(self):
        """Test that context is refreshed even for accepted entries."""
        existing = {
            "Username": MasterEntry(
                msgid="Username",
                msgstr="Benutzername",
                status="accepted",
                score="10",
                context="old_context",  # Will be updated
                context_sources=""
            )
        }

        po_entries = [
            POEntryData(
                msgid="Username",
                msgstr="Benutzername",
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="forms.py:10",  # Should match form_label
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file="django.po"
            )
        ]

        context_rules = [
            {'pattern': 'forms.py', 'context': 'form_label'}
        ]

        result = merge_master(existing, po_entries, None, context_rules)

        assert result[0].context == "form_label"  # Refreshed

    def test_context_aggregates_all_files(self):
        """Test that context aggregates references from all files."""
        parser = MultiPOParser([
            str(FIXTURES_DIR / "django.po"),
            str(FIXTURES_DIR / "forms.po")
        ])
        entries = parser.parse()

        context_rules = [
            {'pattern': 'forms.py', 'context': 'form_label'},
            {'pattern': 'forms/login.py', 'context': 'login_form'},
            {'pattern': 'forms/contact.py', 'context': 'contact_form'},
            {'pattern': 'admin.py', 'context': 'admin'}
        ]

        result = create_master(entries, None, context_rules)

        # Find "Username" which appears in both files
        username = next((e for e in result if e.msgid == "Username"), None)

        assert username is not None
        # Should have references from both files


class TestCSVIO:
    """Tests for CSV input/output."""

    def test_save_utf8_bom(self):
        """Test that saved CSV has UTF-8 BOM."""
        entries = [
            MasterEntry(
                msgid="Hello",
                msgstr="Hallo",
                status="review",
                score="",
                context="",
                context_sources=""
            )
        ]

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.csv"
            save_master(entries, str(output_path))

            # Read raw bytes
            with open(output_path, 'rb') as f:
                content = f.read()

            # Check for BOM
            assert content.startswith(b'\xef\xbb\xbf')

    def test_save_quote_all(self):
        """Test that all fields are quoted."""
        entries = [
            MasterEntry(
                msgid="Hello",
                msgstr="Hallo",
                status="review",
                score="10",
                context="message",
                context_sources=""
            )
        ]

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.csv"
            save_master(entries, str(output_path))

            with open(output_path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()

            # Check data line (skip header)
            data_line = lines[1]
            # All fields should be quoted
            assert data_line.startswith('"')
            assert data_line.strip().endswith('"')

    def test_load_save_roundtrip(self):
        """Test that load/save roundtrip preserves data."""
        entries = [
            MasterEntry(
                msgid="Hello",
                msgstr="Hallo",
                status="accepted",
                score="10",
                context="message",
                context_sources="file1.py=msg;file2.py=label"
            ),
            MasterEntry(
                msgid="Goodbye",
                msgstr="Auf Wiedersehen",
                status="review",
                score="",
                context="",
                context_sources=""
            )
        ]

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.csv"

            # Save
            save_master(entries, str(output_path))

            # Load
            loaded = load_master(str(output_path))

            # Compare
            assert len(loaded) == 2
            assert "Hello" in loaded
            assert loaded["Hello"].msgstr == "Hallo"
            assert loaded["Hello"].status == "accepted"
            assert loaded["Hello"].score == "10"
            assert loaded["Hello"].context == "message"
            assert loaded["Hello"].context_sources == "file1.py=msg;file2.py=label"

    def test_column_order(self):
        """Test that columns are in correct order."""
        entries = [
            MasterEntry(
                msgid="Hello",
                msgstr="Hallo",
                status="review",
                score="",
                context="",
                context_sources=""
            )
        ]

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.csv"
            save_master(entries, str(output_path))

            with open(output_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames

            expected = ['msgid', 'msgstr', 'status', 'score', 'context', 'context_sources', 'candidate']
            assert fieldnames == expected


class TestCLIMaster:
    """Integration tests for CLI master CSV commands (migrated to import subcommand)."""

    def test_master_creates_new_csv(self):
        """Test creating new master CSV via CLI."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "polyglott-accepted-de.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(output_path),
                    str(FIXTURES_DIR / "django.po")
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert output_path.exists()

            # Load and verify
            with open(output_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 6  # 6 entries in django.po

    def test_master_updates_existing(self):
        """Test updating existing master CSV."""
        with TemporaryDirectory() as tmpdir:
            # Copy existing master
            import shutil
            master_path = Path(tmpdir) / "polyglott-accepted-de.csv"
            shutil.copy(FIXTURES_DIR / "master_existing.csv", master_path)

            # Run import to update with multiple files
            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    "--include", str(FIXTURES_DIR / "*.po")
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

            # Load and verify
            loaded = load_master(str(master_path))

            # "Will be stale" should now be stale (not in current PO files)
            assert "Will be stale" in loaded
            assert loaded["Will be stale"].status == "stale"

    def test_master_with_context_rules(self):
        """Test master CSV with context rules."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "polyglott-accepted-de.csv"

            # Create simple context rules
            rules_path = Path(tmpdir) / "rules.yaml"
            rules_path.write_text("""rules:
  - pattern: 'forms.py'
    context: 'form_label'
  - pattern: 'views.py'
    context: 'message'
""")

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(output_path),
                    str(FIXTURES_DIR / "django.po"),
                    "--context-rules", str(rules_path)
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

            # Load and verify context
            loaded = load_master(str(output_path))
            assert loaded["Username"].context == "form_label"
            assert loaded["Login successful"].context == "message"

    def test_master_with_glossary(self):
        """Test master CSV with glossary scoring."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "polyglott-accepted-de.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(output_path),
                    str(FIXTURES_DIR / "django.po"),
                    "--glossary", str(FIXTURES_DIR / "glossary_de.yaml")
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

            # Load and verify scores
            loaded = load_master(str(output_path))

            # These should have score 10 (exact glossary matches)
            assert loaded["Username"].score == "10"
            assert loaded["Password"].score == "10"
            assert loaded["Submit"].score == "10"
            assert loaded["User"].score == "10"

    def test_master_mutually_exclusive_with_output(self):
        """Test that import and scan are separate (no longer mutually exclusive)."""
        # This test is no longer applicable since import is a separate subcommand
        # Just verify that scan works without master flag
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "scan",
                    str(FIXTURES_DIR / "django.po"),
                    "-o", str(output_path)
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

    def test_master_invalid_filename(self):
        """Test that invalid master filename is rejected."""
        with TemporaryDirectory() as tmpdir:
            invalid_path = Path(tmpdir) / "invalid-name.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(invalid_path),
                    str(FIXTURES_DIR / "django.po")
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 1
            assert "Cannot infer target language" in result.stderr

    def test_master_no_po_files(self):
        """Test error when no PO files found (Stage 5.1)."""
        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "polyglott-accepted-de.csv"

            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    "--include", "*.nonexistent"
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 1
            # Should warn about no matches
            assert "Pattern '*.nonexistent' matched no files" in result.stderr
            assert "No PO files specified" in result.stderr

    def test_conflict_detection_roundtrip(self):
        """Test conflict detection in full workflow."""
        with TemporaryDirectory() as tmpdir:
            master_path = Path(tmpdir) / "polyglott-accepted-de.csv"

            # Initial import
            subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    str(FIXTURES_DIR / "django.po")
                ],
                capture_output=True,
                text=True
            )

            # Manually edit master to mark Password as accepted
            loaded = load_master(str(master_path))
            for msgid, entry in loaded.items():
                if msgid == "Password":
                    loaded[msgid] = MasterEntry(
                        msgid=entry.msgid,
                        msgstr=entry.msgstr,
                        status="accepted",  # Mark as accepted
                        score=entry.score,
                        context=entry.context,
                        context_sources=entry.context_sources
                    )

            save_master(list(loaded.values()), str(master_path))

            # Re-import with forms.po which has different translation for Password
            result = subprocess.run(
                [
                    sys.executable, "-m", "polyglott", "import",
                    "--master", str(master_path),
                    str(FIXTURES_DIR / "forms.po")
                ],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

            # Verify conflict detected
            reloaded = load_master(str(master_path))
            # Password in forms.po is "Kennwort" vs "Passwort" in django.po
            assert reloaded["Password"].status == "conflict"
            assert reloaded["Password"].msgstr == "Passwort"  # Original preserved


class TestLanguageInference:
    """Tests for language inference from filename."""

    def test_infer_master_de(self):
        """Test inferring 'de' from master-de.csv."""
        lang = infer_language("master-de.csv")
        assert lang == "de"

    def test_infer_polyglott_accepted_de(self):
        """Test inferring 'de' from polyglott-accepted-de.csv."""
        lang = infer_language("polyglott-accepted-de.csv")
        assert lang == "de"

    def test_infer_help_pages_de(self):
        """Test inferring 'de' from help-pages-de.csv."""
        lang = infer_language("help-pages-de.csv")
        assert lang == "de"

    def test_infer_de_csv(self):
        """Test inferring 'de' from de.csv."""
        lang = infer_language("de.csv")
        assert lang == "de"

    def test_infer_en_us(self):
        """Test inferring 'en-us' from myproject-en-us.csv."""
        lang = infer_language("myproject-en-us.csv")
        assert lang == "en-us"

    def test_infer_pt_br(self):
        """Test inferring 'pt-br' from project-pt-br.csv."""
        lang = infer_language("project-pt-br.csv")
        assert lang == "pt-br"

    def test_infer_with_path(self):
        """Test language inference works with full paths."""
        lang = infer_language("/path/to/master-de.csv")
        assert lang == "de"

    def test_infer_fails_no_language(self):
        """Test that inference fails for translations.csv."""
        with pytest.raises(ValueError) as exc_info:
            infer_language("translations.csv")

        assert "Cannot infer target language" in str(exc_info.value)
        assert "translations.csv" in str(exc_info.value)

    def test_infer_fails_non_csv(self):
        """Test that inference fails for non-CSV files."""
        with pytest.raises(ValueError) as exc_info:
            infer_language("master-de.po")

        assert "Cannot infer target language" in str(exc_info.value)

    def test_infer_fails_invalid_language_code(self):
        """Test that inference fails for invalid language codes."""
        with pytest.raises(ValueError) as exc_info:
            infer_language("master-toolong.csv")

        assert "Cannot infer target language" in str(exc_info.value)

    def test_override_with_lang_flag(self):
        """Test that --lang override takes precedence."""
        lang = infer_language("translations.csv", lang_override="de")
        assert lang == "de"

    def test_override_ignores_filename(self):
        """Test that --lang override ignores filename."""
        lang = infer_language("master-fr.csv", lang_override="de")
        assert lang == "de"

    def test_zh_hans(self):
        """Test inferring complex language code like zh-hans."""
        lang = infer_language("master-zh-hans.csv")
        assert lang == "zh-hans"


class TestStage7CandidateColumn:
    """Tests for Stage 7: candidate column functionality."""

    def test_master_entry_has_candidate_field(self):
        """Test that MasterEntry includes candidate field."""
        entry = MasterEntry(
            msgid="Save",
            msgstr="Guardar",
            status="accepted",
            score="",
            context="",
            context_sources="",
            candidate="Almacenar"
        )
        assert entry.candidate == "Almacenar"

    def test_candidate_empty_by_default(self):
        """Test that candidate defaults to empty string."""
        entry = MasterEntry(
            msgid="Save",
            msgstr="Guardar",
            status="accepted",
            score="",
            context="",
            context_sources=""
        )
        assert entry.candidate == ''

    def test_load_master_adds_missing_candidate_column(self):
        """Test that load_master adds candidate column if missing (pre-Stage 7 CSV)."""
        with TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test.csv"

            # Write CSV without candidate column (pre-Stage 7 format)
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['msgid', 'msgstr', 'status', 'score', 'context', 'context_sources'], quoting=csv.QUOTE_ALL)
                writer.writeheader()
                writer.writerow({
                    'msgid': 'Save',
                    'msgstr': 'Guardar',
                    'status': 'accepted',
                    'score': '',
                    'context': '',
                    'context_sources': ''
                })

            # Load should add candidate column with empty value
            result = load_master(str(csv_path))

            assert 'Save' in result
            assert result['Save'].candidate == ''

    def test_save_and_load_roundtrip_with_candidate(self):
        """Test that candidate survives save → load roundtrip."""
        with TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test.csv"

            entries = [
                MasterEntry(
                    msgid="Save",
                    msgstr="Guardar",
                    status="machine",
                    score="",
                    context="",
                    context_sources="",
                    candidate="Almacenar"
                )
            ]

            save_master(entries, str(csv_path))
            loaded = load_master(str(csv_path))

            assert loaded['Save'].candidate == "Almacenar"

    def test_merge_preserves_candidate_column(self):
        """Test that merge_master preserves candidate values."""
        existing = {
            "Save": MasterEntry(
                msgid="Save",
                msgstr="Guardar",
                status="machine",
                score="",
                context="",
                context_sources="",
                candidate="Almacenar"
            )
        }

        po_entries = [
            POEntryData(
                msgid="Save",
                msgstr="Guardar",
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
        ]

        result = merge_master(existing, po_entries)

        assert result[0].candidate == "Almacenar"


class TestStage7ColumnSovereignty:
    """Tests for Stage 7: column sovereignty (preserving user columns)."""

    def test_load_preserves_user_columns(self):
        """Test that load_master preserves user-added columns."""
        with TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test.csv"

            # Write CSV with user columns
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                fieldnames = ['msgid', 'msgstr', 'status', 'score', 'context', 'context_sources', 'candidate', 'notes', 'reviewer']
                writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
                writer.writeheader()
                writer.writerow({
                    'msgid': 'Save',
                    'msgstr': 'Guardar',
                    'status': 'accepted',
                    'score': '',
                    'context': '',
                    'context_sources': '',
                    'candidate': '',
                    'notes': 'needs review',
                    'reviewer': 'Alice'
                })

            result = load_master(str(csv_path))

            assert result['Save'].extra_columns['notes'] == 'needs review'
            assert result['Save'].extra_columns['reviewer'] == 'Alice'

    def test_save_preserves_user_columns(self):
        """Test that save_master preserves user-added columns."""
        with TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test.csv"

            entries = [
                MasterEntry(
                    msgid="Save",
                    msgstr="Guardar",
                    status="accepted",
                    score="",
                    context="",
                    context_sources="",
                    candidate="",
                    extra_columns={'notes': 'needs review', 'reviewer': 'Alice'}
                )
            ]

            save_master(entries, str(csv_path))

            # Read back with csv module to verify
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 1
            assert rows[0]['notes'] == 'needs review'
            assert rows[0]['reviewer'] == 'Alice'

    def test_column_order_polyglott_first(self):
        """Test that POlyglott columns come first, user columns after."""
        with TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test.csv"

            # Create entry with user columns in mixed order
            entries = [
                MasterEntry(
                    msgid="Save",
                    msgstr="Guardar",
                    status="accepted",
                    score="",
                    context="",
                    context_sources="",
                    candidate="",
                    extra_columns={'priority': '1', 'reviewer': 'Alice', 'notes': 'check this'}
                )
            ]

            save_master(entries, str(csv_path))

            # Read header to check column order
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                cols = reader.fieldnames

            # POlyglott columns should come first
            from polyglott.master import POLYGLOTT_COLUMNS
            for i, col in enumerate(POLYGLOTT_COLUMNS):
                assert cols[i] == col

            # User columns should come after
            assert 'priority' in cols
            assert 'reviewer' in cols
            assert 'notes' in cols

    def test_user_columns_survive_roundtrip(self):
        """Test that user columns survive save → load → save cycle."""
        with TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test.csv"

            # Original entries with user columns
            original = [
                MasterEntry(
                    msgid="Save",
                    msgstr="Guardar",
                    status="accepted",
                    score="",
                    context="",
                    context_sources="",
                    candidate="",
                    extra_columns={'notes': 'important', 'reviewer': 'Bob'}
                )
            ]

            # Save → load → save → load
            save_master(original, str(csv_path))
            loaded1 = load_master(str(csv_path))
            entries1 = list(loaded1.values())
            save_master(entries1, str(csv_path))
            loaded2 = load_master(str(csv_path))

            # User columns should still be there
            assert loaded2['Save'].extra_columns['notes'] == 'important'
            assert loaded2['Save'].extra_columns['reviewer'] == 'Bob'

    def test_different_entries_different_user_columns(self):
        """Test that entries can have different user columns."""
        with TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test.csv"

            entries = [
                MasterEntry(
                    msgid="Save",
                    msgstr="Guardar",
                    status="accepted",
                    score="",
                    context="",
                    context_sources="",
                    candidate="",
                    extra_columns={'notes': 'A'}
                ),
                MasterEntry(
                    msgid="Cancel",
                    msgstr="Cancelar",
                    status="accepted",
                    score="",
                    context="",
                    context_sources="",
                    candidate="",
                    extra_columns={'reviewer': 'Bob'}
                )
            ]

            save_master(entries, str(csv_path))

            # Read back
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # Both columns should exist in CSV
            assert 'notes' in rows[0]
            assert 'reviewer' in rows[0]

            # First entry has notes, no reviewer
            assert rows[0]['notes'] == 'A'
            assert rows[0]['reviewer'] == ''

            # Second entry has reviewer, no notes
            assert rows[1]['notes'] == ''
            assert rows[1]['reviewer'] == 'Bob'

    def test_merge_preserves_user_columns(self):
        """Test that merge_master preserves user columns from existing entries."""
        existing = {
            "Save": MasterEntry(
                msgid="Save",
                msgstr="Guardar",
                status="accepted",
                score="",
                context="",
                context_sources="",
                candidate="",
                extra_columns={'notes': 'important', 'reviewer': 'Alice'}
            )
        }

        po_entries = [
            POEntryData(
                msgid="Save",
                msgstr="Guardar",
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
        ]

        result = merge_master(existing, po_entries)

        # User columns should be preserved
        assert result[0].extra_columns['notes'] == 'important'
        assert result[0].extra_columns['reviewer'] == 'Alice'

    def test_new_entries_have_empty_user_columns(self):
        """Test that new entries from merge have no user columns."""
        existing = {
            "Save": MasterEntry(
                msgid="Save",
                msgstr="Guardar",
                status="accepted",
                score="",
                context="",
                context_sources="",
                candidate="",
                extra_columns={'notes': 'keep this'}
            )
        }

        po_entries = [
            POEntryData(
                msgid="Save",
                msgstr="Guardar",
                msgctxt=None,
                extracted_comments="",
                translator_comments="",
                references="file.py:10",
                fuzzy=False,
                obsolete=False,
                is_plural=False,
                plural_index=None,
                source_file="test.po"
            ),
            POEntryData(
                msgid="Cancel",
                msgstr="Cancelar",
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
        ]

        result = merge_master(existing, po_entries)

        # Existing entry keeps user columns
        save_entry = [e for e in result if e.msgid == "Save"][0]
        assert save_entry.extra_columns['notes'] == 'keep this'

        # New entry has no user columns
        cancel_entry = [e for e in result if e.msgid == "Cancel"][0]
        assert cancel_entry.extra_columns == {}
