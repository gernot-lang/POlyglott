"""PO file parser using polib."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import polib


@dataclass
class POEntryData:
    """Represents a single PO entry with all metadata."""

    msgid: str
    msgstr: str
    msgctxt: Optional[str]
    extracted_comments: str
    translator_comments: str
    references: str
    fuzzy: bool
    obsolete: bool
    is_plural: bool
    plural_index: Optional[int]
    source_file: Optional[str] = None


@dataclass
class POStatistics:
    """Statistics for a PO file."""

    total: int
    untranslated: int
    fuzzy: int
    plurals: int


class POParser:
    """Parser for gettext PO files."""

    def __init__(self, filepath: str):
        """Initialize parser with a PO file path.

        Args:
            filepath: Path to the PO file

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file is malformed
        """
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"PO file not found: {filepath}")

        try:
            self.po = polib.pofile(str(self.filepath))
        except Exception as e:
            raise ValueError(f"Failed to parse PO file: {e}")

    def parse(self, source_file: Optional[str] = None) -> List[POEntryData]:
        """Parse the PO file and extract all entries.

        Args:
            source_file: Optional source file name for multi-file mode

        Returns:
            List of POEntryData objects
        """
        entries = []

        # Process regular entries (skip obsolete ones as they're handled separately)
        for entry in self.po:
            if not entry.obsolete:
                entries.extend(self._process_entry(entry, source_file))

        # Process obsolete entries
        for entry in self.po.obsolete_entries():
            entries.extend(self._process_entry(entry, source_file, obsolete=True))

        return entries

    def _process_entry(
            self,
            entry: polib.POEntry,
            source_file: Optional[str] = None,
            obsolete: bool = False
    ) -> List[POEntryData]:
        """Process a single PO entry, handling plurals.

        Args:
            entry: The polib POEntry object
            source_file: Optional source file name
            obsolete: Whether this is an obsolete entry

        Returns:
            List of POEntryData (multiple items for plurals)
        """
        # Check if this is a plural entry
        is_plural = bool(entry.msgid_plural)

        # Extract common metadata
        msgctxt = entry.msgctxt or None
        extracted_comments = entry.comment or ""
        translator_comments = entry.tcomment or ""

        # Join references (list of tuples) into space-separated string
        references = " ".join(f"{ref[0]}:{ref[1]}" for ref in entry.occurrences)

        # Check fuzzy flag
        fuzzy = "fuzzy" in entry.flags

        if is_plural:
            # Create one entry per plural form
            result = []
            msgid = entry.msgid_plural  # Use plural form as msgid

            # msgstr_plural is a dict: {0: "form0", 1: "form1", ...}
            for idx, msgstr in entry.msgstr_plural.items():
                result.append(POEntryData(
                    msgid=msgid,
                    msgstr=msgstr,
                    msgctxt=msgctxt,
                    extracted_comments=extracted_comments,
                    translator_comments=translator_comments,
                    references=references,
                    fuzzy=fuzzy,
                    obsolete=obsolete,
                    is_plural=True,
                    plural_index=idx,
                    source_file=source_file
                ))
            return result
        else:
            # Single entry
            return [POEntryData(
                msgid=entry.msgid,
                msgstr=entry.msgstr,
                msgctxt=msgctxt,
                extracted_comments=extracted_comments,
                translator_comments=translator_comments,
                references=references,
                fuzzy=fuzzy,
                obsolete=obsolete,
                is_plural=False,
                plural_index=None,
                source_file=source_file
            )]

    def get_statistics(self) -> POStatistics:
        """Calculate statistics for the PO file.

        Returns:
            POStatistics object with counts
        """
        total = len(self.po)
        untranslated = len(self.po.untranslated_entries())
        fuzzy = len(self.po.fuzzy_entries())

        # Count plural entries
        plurals = sum(1 for entry in self.po if entry.msgid_plural)

        return POStatistics(
            total=total,
            untranslated=untranslated,
            fuzzy=fuzzy,
            plurals=plurals
        )


class MultiPOParser:
    """Parser for multiple PO files."""

    def __init__(self, filepaths: List[str]):
        """Initialize parser with multiple PO file paths.

        Args:
            filepaths: List of paths to PO files
        """
        self.filepaths = filepaths

    def parse(self) -> List[POEntryData]:
        """Parse all PO files and combine entries.

        Returns:
            List of POEntryData objects from all files
        """
        all_entries = []

        for filepath in self.filepaths:
            parser = POParser(filepath)
            # Pass the filename (not full path) as source_file
            source_file = Path(filepath).name
            entries = parser.parse(source_file=source_file)
            all_entries.extend(entries)

        return all_entries

    def get_combined_statistics(self) -> POStatistics:
        """Calculate combined statistics across all files.

        Returns:
            POStatistics object with combined counts
        """
        total = 0
        untranslated = 0
        fuzzy = 0
        plurals = 0

        for filepath in self.filepaths:
            parser = POParser(filepath)
            stats = parser.get_statistics()
            total += stats.total
            untranslated += stats.untranslated
            fuzzy += stats.fuzzy
            plurals += stats.plurals

        return POStatistics(
            total=total,
            untranslated=untranslated,
            fuzzy=fuzzy,
            plurals=plurals
        )
