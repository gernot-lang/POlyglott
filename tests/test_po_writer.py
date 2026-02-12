"""Tests for PO file writer (export functionality)."""

from pathlib import Path
from tempfile import TemporaryDirectory

import polib
import pytest

from polyglott.master import MasterEntry
from polyglott.po_writer import export_to_po, ExportResult


class TestExportBasics:
    """Test basic export functionality."""

    def test_accepted_entry_written_to_po(self):
        """Test that accepted entry is written to PO file."""
        with TemporaryDirectory() as tmpdir:
            po_path = Path(tmpdir) / "test.po"

            # Create simple PO file
            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr=""))
            po.save(str(po_path))

            # Master with accepted translation
            master = [
                MasterEntry(
                    msgid="Hello",
                    msgstr="Hallo",
                    status="accepted",
                    score="",
                    context="",
                    context_sources=""
                )
            ]

            result = export_to_po(master, str(po_path), {"accepted"})

            assert result.writes == 1
            assert result.overwrites == 0

            # Verify PO file was updated
            po_loaded = polib.pofile(str(po_path))
            entry = po_loaded.find("Hello")
            assert entry.msgstr == "Hallo"
            assert "fuzzy" not in entry.flags

    def test_entry_not_in_master_untouched(self):
        """Test that entries not in master are left untouched."""
        with TemporaryDirectory() as tmpdir:
            po_path = Path(tmpdir) / "test.po"

            # Create PO file with entry not in master
            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr="Old Translation"))
            po.append(polib.POEntry(msgid="World", msgstr="Welt"))
            po.save(str(po_path))

            # Master with only "Hello"
            master = [
                MasterEntry(
                    msgid="Hello",
                    msgstr="Hallo",
                    status="accepted",
                    score="",
                    context="",
                    context_sources=""
                )
            ]

            result = export_to_po(master, str(po_path), {"accepted"})

            # "World" should be skipped
            assert result.skips == 1

            # Verify "World" was not modified
            po_loaded = polib.pofile(str(po_path))
            world_entry = po_loaded.find("World")
            assert world_entry.msgstr == "Welt"

    def test_empty_msgstr_in_master_skipped(self):
        """Test that entries with empty msgstr in master are not exported."""
        with TemporaryDirectory() as tmpdir:
            po_path = Path(tmpdir) / "test.po"

            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr="Old"))
            po.save(str(po_path))

            # Master with empty msgstr
            master = [
                MasterEntry(
                    msgid="Hello",
                    msgstr="",
                    status="accepted",
                    score="",
                    context="",
                    context_sources=""
                )
            ]

            result = export_to_po(master, str(po_path), {"accepted"})

            assert result.skips == 1

            # PO entry should remain unchanged
            po_loaded = polib.pofile(str(po_path))
            entry = po_loaded.find("Hello")
            assert entry.msgstr == "Old"

    def test_overwrite_existing_msgstr(self):
        """Test that existing different msgstr is overwritten."""
        with TemporaryDirectory() as tmpdir:
            po_path = Path(tmpdir) / "test.po"

            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr="Old Translation"))
            po.save(str(po_path))

            master = [
                MasterEntry(
                    msgid="Hello",
                    msgstr="New Translation",
                    status="accepted",
                    score="",
                    context="",
                    context_sources=""
                )
            ]

            result = export_to_po(master, str(po_path), {"accepted"})

            assert result.writes == 0
            assert result.overwrites == 1

            # Verify msgstr was updated
            po_loaded = polib.pofile(str(po_path))
            entry = po_loaded.find("Hello")
            assert entry.msgstr == "New Translation"


class TestStatusFiltering:
    """Test status filtering logic."""

    def test_default_only_accepted(self):
        """Test that by default only accepted entries are exported."""
        with TemporaryDirectory() as tmpdir:
            po_path = Path(tmpdir) / "test.po"

            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr=""))
            po.append(polib.POEntry(msgid="World", msgstr=""))
            po.append(polib.POEntry(msgid="Goodbye", msgstr=""))
            po.save(str(po_path))

            master = [
                MasterEntry(msgid="Hello", msgstr="Hallo", status="accepted", score="", context="", context_sources=""),
                MasterEntry(msgid="World", msgstr="Welt", status="machine", score="", context="", context_sources=""),
                MasterEntry(msgid="Goodbye", msgstr="Tschüss", status="review", score="", context="", context_sources=""),
            ]

            result = export_to_po(master, str(po_path), {"accepted"})

            # Only accepted should be written
            assert result.writes == 1

            po_loaded = polib.pofile(str(po_path))
            assert po_loaded.find("Hello").msgstr == "Hallo"
            assert po_loaded.find("World").msgstr == ""
            assert po_loaded.find("Goodbye").msgstr == ""

    def test_multiple_statuses(self):
        """Test exporting multiple statuses."""
        with TemporaryDirectory() as tmpdir:
            po_path = Path(tmpdir) / "test.po"

            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr=""))
            po.append(polib.POEntry(msgid="World", msgstr=""))
            po.append(polib.POEntry(msgid="Goodbye", msgstr=""))
            po.save(str(po_path))

            master = [
                MasterEntry(msgid="Hello", msgstr="Hallo", status="accepted", score="", context="", context_sources=""),
                MasterEntry(msgid="World", msgstr="Welt", status="machine", score="", context="", context_sources=""),
                MasterEntry(msgid="Goodbye", msgstr="Tschüss", status="review", score="", context="", context_sources=""),
            ]

            result = export_to_po(master, str(po_path), {"accepted", "machine"})

            # Both accepted and machine should be written
            assert result.writes == 2

            po_loaded = polib.pofile(str(po_path))
            assert po_loaded.find("Hello").msgstr == "Hallo"
            assert po_loaded.find("World").msgstr == "Welt"
            assert po_loaded.find("Goodbye").msgstr == ""


class TestFuzzyFlagHandling:
    """Test fuzzy flag handling."""

    def test_accepted_clears_fuzzy(self):
        """Test that accepted status clears fuzzy flag."""
        with TemporaryDirectory() as tmpdir:
            po_path = Path(tmpdir) / "test.po"

            po = polib.POFile()
            entry = polib.POEntry(msgid="Hello", msgstr="Old", flags=["fuzzy"])
            po.append(entry)
            po.save(str(po_path))

            master = [
                MasterEntry(msgid="Hello", msgstr="Hallo", status="accepted", score="", context="", context_sources="")
            ]

            export_to_po(master, str(po_path), {"accepted"})

            po_loaded = polib.pofile(str(po_path))
            entry = po_loaded.find("Hello")
            assert "fuzzy" not in entry.flags

    def test_machine_sets_fuzzy(self):
        """Test that machine status sets fuzzy flag."""
        with TemporaryDirectory() as tmpdir:
            po_path = Path(tmpdir) / "test.po"

            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr=""))
            po.save(str(po_path))

            master = [
                MasterEntry(msgid="Hello", msgstr="Hallo", status="machine", score="", context="", context_sources="")
            ]

            export_to_po(master, str(po_path), {"machine"})

            po_loaded = polib.pofile(str(po_path))
            entry = po_loaded.find("Hello")
            assert "fuzzy" in entry.flags

    def test_review_leaves_fuzzy_unchanged(self):
        """Test that review status leaves fuzzy flag unchanged."""
        with TemporaryDirectory() as tmpdir:
            po_path = Path(tmpdir) / "test.po"

            # Test with fuzzy flag present
            po = polib.POFile()
            entry = polib.POEntry(msgid="Hello", msgstr="Old", flags=["fuzzy"])
            po.append(entry)
            po.save(str(po_path))

            master = [
                MasterEntry(msgid="Hello", msgstr="Hallo", status="review", score="", context="", context_sources="")
            ]

            export_to_po(master, str(po_path), {"review"})

            po_loaded = polib.pofile(str(po_path))
            entry = po_loaded.find("Hello")
            assert "fuzzy" in entry.flags

            # Test with fuzzy flag absent
            po = polib.POFile()
            entry = polib.POEntry(msgid="World", msgstr="")
            po.append(entry)
            po.save(str(po_path))

            master = [
                MasterEntry(msgid="World", msgstr="Welt", status="review", score="", context="", context_sources="")
            ]

            export_to_po(master, str(po_path), {"review"})

            po_loaded = polib.pofile(str(po_path))
            entry = po_loaded.find("World")
            assert "fuzzy" not in entry.flags


class TestDryRun:
    """Test dry run mode."""

    def test_dry_run_no_modification(self):
        """Test that dry run doesn't modify files."""
        with TemporaryDirectory() as tmpdir:
            po_path = Path(tmpdir) / "test.po"

            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr=""))
            po.save(str(po_path))

            master = [
                MasterEntry(msgid="Hello", msgstr="Hallo", status="accepted", score="", context="", context_sources="")
            ]

            result = export_to_po(master, str(po_path), {"accepted"}, dry_run=True)

            # Should report what would happen
            assert result.writes == 1

            # But file should not be modified
            po_loaded = polib.pofile(str(po_path))
            entry = po_loaded.find("Hello")
            assert entry.msgstr == ""

    def test_dry_run_correct_summary(self):
        """Test that dry run produces correct summary."""
        with TemporaryDirectory() as tmpdir:
            po_path = Path(tmpdir) / "test.po"

            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr="Old"))
            po.append(polib.POEntry(msgid="World", msgstr=""))
            po.save(str(po_path))

            master = [
                MasterEntry(msgid="Hello", msgstr="New", status="accepted", score="", context="", context_sources=""),
                MasterEntry(msgid="World", msgstr="Welt", status="accepted", score="", context="", context_sources=""),
            ]

            result = export_to_po(master, str(po_path), {"accepted"}, dry_run=True)

            assert result.writes == 1  # World
            assert result.overwrites == 1  # Hello


class TestVerboseOutput:
    """Test verbose output."""

    def test_verbose_generates_details(self):
        """Test that verbose mode generates per-entry details."""
        with TemporaryDirectory() as tmpdir:
            po_path = Path(tmpdir) / "test.po"

            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr=""))
            po.save(str(po_path))

            master = [
                MasterEntry(msgid="Hello", msgstr="Hallo", status="accepted", score="", context="", context_sources="")
            ]

            result = export_to_po(master, str(po_path), {"accepted"}, verbose=True)

            assert len(result.details) > 0
            assert any("WRITE" in detail and "Hello" in detail for detail in result.details)

    def test_verbose_skip_messages(self):
        """Test that verbose mode includes skip messages."""
        with TemporaryDirectory() as tmpdir:
            po_path = Path(tmpdir) / "test.po"

            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr=""))
            po.append(polib.POEntry(msgid="World", msgstr=""))
            po.save(str(po_path))

            # Master has only "Hello"
            master = [
                MasterEntry(msgid="Hello", msgstr="Hallo", status="accepted", score="", context="", context_sources="")
            ]

            result = export_to_po(master, str(po_path), {"accepted"}, verbose=True)

            # Should have skip message for "World"
            assert any("SKIP" in detail and "not in master" in detail for detail in result.details)

    def test_verbose_overwrite_messages(self):
        """Test that verbose mode shows overwrites correctly."""
        with TemporaryDirectory() as tmpdir:
            po_path = Path(tmpdir) / "test.po"

            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr="Old Translation"))
            po.save(str(po_path))

            master = [
                MasterEntry(msgid="Hello", msgstr="New Translation", status="accepted", score="", context="", context_sources="")
            ]

            result = export_to_po(master, str(po_path), {"accepted"}, verbose=True)

            assert any("OVERWRITE" in detail and "Old Translation" in detail and "New Translation" in detail
                       for detail in result.details)


class TestFullPathsInOutput:
    """Test that full paths are used in output."""

    def test_full_path_in_details(self):
        """Test that verbose output uses full file paths."""
        with TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "locale" / "de" / "LC_MESSAGES"
            subdir.mkdir(parents=True)
            po_path = subdir / "django.po"

            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr=""))
            po.save(str(po_path))

            master = [
                MasterEntry(msgid="Hello", msgstr="Hallo", status="accepted", score="", context="", context_sources="")
            ]

            result = export_to_po(master, str(po_path), {"accepted"}, verbose=True)

            # Should contain full path, not just "django.po"
            assert any(str(po_path) in detail for detail in result.details)
            assert not any(detail.startswith("WRITE    django.po:") for detail in result.details)


class TestIdempotency:
    """Test that export is idempotent in its reporting."""

    def test_idempotent_export_counts(self):
        """Test that running export twice reports 0 writes on second run."""
        with TemporaryDirectory() as tmpdir:
            po_path = Path(tmpdir) / "test.po"

            # Create PO file with empty msgstr
            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr=""))
            po.save(str(po_path))

            master = [
                MasterEntry(msgid="Hello", msgstr="Hallo", status="accepted", score="", context="", context_sources="")
            ]

            # First export: should write the translation
            result1 = export_to_po(master, str(po_path), {"accepted"})
            assert result1.writes == 1
            assert result1.overwrites == 0
            assert result1.skips == 0

            # Second export: PO now matches master, should skip
            result2 = export_to_po(master, str(po_path), {"accepted"})
            assert result2.writes == 0  # Should be 0, not 1
            assert result2.overwrites == 0
            assert result2.skips == 1  # Previously written entry now skipped

    def test_skip_when_already_matches(self):
        """Test that entries already matching master are skipped, not written."""
        with TemporaryDirectory() as tmpdir:
            po_path = Path(tmpdir) / "test.po"

            # Create PO file with translation already matching master
            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr="Hallo"))
            po.save(str(po_path))

            master = [
                MasterEntry(msgid="Hello", msgstr="Hallo", status="accepted", score="", context="", context_sources="")
            ]

            # Export should skip (already matches)
            result = export_to_po(master, str(po_path), {"accepted"})
            assert result.writes == 0
            assert result.overwrites == 0
            assert result.skips == 1

    def test_skip_verbose_output(self):
        """Test that skip actions appear in verbose output."""
        with TemporaryDirectory() as tmpdir:
            po_path = Path(tmpdir) / "test.po"

            po = polib.POFile()
            po.append(polib.POEntry(msgid="Hello", msgstr="Hallo"))
            po.save(str(po_path))

            master = [
                MasterEntry(msgid="Hello", msgstr="Hallo", status="accepted", score="", context="", context_sources="")
            ]

            result = export_to_po(master, str(po_path), {"accepted"}, verbose=True)

            # Should have skip message
            assert any("SKIP" in detail and "already matches master" in detail for detail in result.details)
