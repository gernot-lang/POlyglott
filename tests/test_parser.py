"""Tests for PO file parser."""

import pytest
from pathlib import Path

from polyglott.parser import POParser, MultiPOParser, POEntryData, POStatistics


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestPOParser:
    """Test suite for POParser."""

    def test_parse_simple_file(self):
        """Test parsing a simple PO file."""
        parser = POParser(FIXTURES_DIR / "simple.po")
        entries = parser.parse()

        # Should have 4 entries (excluding header)
        assert len(entries) == 4

        # Check first translated entry
        hello = next(e for e in entries if e.msgid == "Hello")
        assert hello.msgstr == "Hallo"
        assert hello.references == "main.py:10"
        assert not hello.fuzzy
        assert not hello.obsolete
        assert not hello.is_plural

    def test_parse_untranslated_entries(self):
        """Test detection of untranslated entries."""
        parser = POParser(FIXTURES_DIR / "simple.po")
        entries = parser.parse()

        # Find untranslated entries
        untranslated = [e for e in entries if e.msgstr == ""]
        assert len(untranslated) == 2

        # Check specific untranslated entry
        goodbye = next(e for e in entries if e.msgid == "Goodbye")
        assert goodbye.msgstr == ""

    def test_parse_complex_metadata(self):
        """Test extraction of all metadata types."""
        parser = POParser(FIXTURES_DIR / "complex.po")
        entries = parser.parse()

        # Find entry with extracted comment
        simple = next(e for e in entries if e.msgid == "Simple message")
        assert "Extracted comment" in simple.extracted_comments
        assert simple.references == "views.py:42 templates/home.html:15"

        # Find entry with context
        home = next(e for e in entries if e.msgid == "Home")
        assert home.msgctxt == "navigation"
        assert home.msgstr == "Start"

    def test_parse_plural_forms(self):
        """Test handling of plural entries."""
        parser = POParser(FIXTURES_DIR / "complex.po")
        entries = parser.parse()

        # Find plural entries for "Item"
        items = [e for e in entries if e.msgid == "Items" and e.is_plural]
        assert len(items) == 2  # Two plural forms

        # Check plural form 0
        item_0 = next(e for e in items if e.plural_index == 0)
        assert item_0.msgstr == "Gegenstand"
        assert item_0.is_plural

        # Check plural form 1
        item_1 = next(e for e in items if e.plural_index == 1)
        assert item_1.msgstr == "Gegenstände"

    def test_parse_fuzzy_flag(self):
        """Test detection of fuzzy translations."""
        parser = POParser(FIXTURES_DIR / "complex.po")
        entries = parser.parse()

        # Find fuzzy entries
        fuzzy_entries = [e for e in entries if e.fuzzy]
        assert len(fuzzy_entries) >= 2  # At least 2 fuzzy entries

        # Check specific fuzzy entry
        fuzzy_untrans = next(e for e in entries if e.msgid == "Fuzzy untranslated")
        assert fuzzy_untrans.fuzzy
        assert fuzzy_untrans.msgstr == ""

    def test_parse_obsolete_entries(self):
        """Test handling of obsolete entries."""
        parser = POParser(FIXTURES_DIR / "complex.po")
        entries = parser.parse()

        # Find obsolete entries
        obsolete = [e for e in entries if e.obsolete]
        assert len(obsolete) >= 1

        # Check specific obsolete entry
        old = next(e for e in entries if e.msgid == "Old message")
        assert old.obsolete
        assert old.msgstr == "Alte Nachricht"

    def test_parse_unicode_content(self):
        """Test handling of Unicode characters."""
        parser = POParser(FIXTURES_DIR / "unicode.po")
        entries = parser.parse()

        # German umlauts
        german = next(e for e in entries if e.msgid == "German umlauts")
        assert "Äpfel" in german.msgstr
        assert "Straße" in german.msgstr

        # Emoji
        emoji = next(e for e in entries if e.msgid == "Emoji support")
        assert "🎉" in emoji.msgstr
        assert "🚀" in emoji.msgstr

        # CJK characters
        chinese = next(e for e in entries if e.msgid == "Chinese characters")
        assert "你好世界" in chinese.msgstr

        # Arabic
        arabic = next(e for e in entries if e.msgid == "Arabic script")
        assert "مرحبا" in arabic.msgstr

    def test_parse_empty_file(self):
        """Test parsing an empty PO file (header only)."""
        parser = POParser(FIXTURES_DIR / "empty.po")
        entries = parser.parse()

        # Should have 0 entries (header doesn't count)
        assert len(entries) == 0

    def test_parse_with_source_file(self):
        """Test parsing with source_file parameter."""
        parser = POParser(FIXTURES_DIR / "simple.po")
        entries = parser.parse(source_file="test.po")

        # All entries should have source_file set
        assert all(e.source_file == "test.po" for e in entries)

    def test_get_statistics(self):
        """Test statistics calculation."""
        parser = POParser(FIXTURES_DIR / "simple.po")
        stats = parser.get_statistics()

        assert stats.total == 4
        assert stats.untranslated == 2
        assert stats.fuzzy == 0
        assert stats.plurals == 0

    def test_file_not_found(self):
        """Test error handling for missing file."""
        with pytest.raises(FileNotFoundError):
            POParser("nonexistent.po")

    def test_malformed_file(self):
        """Test error handling for malformed PO file."""
        with pytest.raises(ValueError):
            POParser(FIXTURES_DIR / "malformed.po")


class TestMultiPOParser:
    """Test suite for MultiPOParser."""

    def test_parse_multiple_files(self):
        """Test parsing multiple PO files."""
        files = [
            str(FIXTURES_DIR / "simple.po"),
            str(FIXTURES_DIR / "unicode.po"),
        ]
        parser = MultiPOParser(files)
        entries = parser.parse()

        # Should have entries from both files
        # simple.po has 4, unicode.po has 6
        assert len(entries) == 10

        # Check source_file is set
        simple_entries = [e for e in entries if e.source_file == "simple.po"]
        unicode_entries = [e for e in entries if e.source_file == "unicode.po"]

        assert len(simple_entries) == 4
        assert len(unicode_entries) == 6

    def test_combined_statistics(self):
        """Test combined statistics across multiple files."""
        files = [
            str(FIXTURES_DIR / "simple.po"),
            str(FIXTURES_DIR / "complex.po"),
        ]
        parser = MultiPOParser(files)
        stats = parser.get_combined_statistics()

        # simple.po: 4 total, 2 untranslated
        # complex.po: varies, but has plurals and fuzzy
        assert stats.total >= 4
        assert stats.untranslated >= 2
        assert stats.plurals >= 2

    def test_empty_file_list(self):
        """Test parsing with empty file list."""
        parser = MultiPOParser([])
        entries = parser.parse()
        assert len(entries) == 0

        stats = parser.get_combined_statistics()
        assert stats.total == 0
        assert stats.untranslated == 0
