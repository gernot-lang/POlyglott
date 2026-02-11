"""CSV exporter for PO file data."""

import sys
from typing import List, Optional, TextIO

import pandas as pd

from polyglott.parser import POEntryData


def export_to_csv(
        entries: List[POEntryData],
        output_file: Optional[str] = None,
        sort_by: Optional[str] = None,
        multi_file: bool = False
) -> None:
    """Export PO entries to CSV format.

    Args:
        entries: List of POEntryData objects to export
        output_file: Output file path (None for stdout)
        sort_by: Optional field name to sort by
        multi_file: Whether to include source_file column

    Raises:
        ValueError: If sort_by field doesn't exist
    """
    if not entries:
        # Handle empty case - write headers only
        if multi_file:
            columns = [
                "source_file", "msgid", "msgstr", "msgctxt",
                "extracted_comments", "translator_comments", "references",
                "fuzzy", "obsolete", "is_plural", "plural_index"
            ]
        else:
            columns = [
                "msgid", "msgstr", "msgctxt",
                "extracted_comments", "translator_comments", "references",
                "fuzzy", "obsolete", "is_plural", "plural_index"
            ]
        df = pd.DataFrame(columns=columns)
    else:
        # Convert entries to DataFrame
        data = []
        for entry in entries:
            row = {
                "msgid": entry.msgid,
                "msgstr": entry.msgstr,
                "msgctxt": entry.msgctxt if entry.msgctxt is not None else "",
                "extracted_comments": entry.extracted_comments,
                "translator_comments": entry.translator_comments,
                "references": entry.references,
                "fuzzy": entry.fuzzy,
                "obsolete": entry.obsolete,
                "is_plural": entry.is_plural,
                "plural_index": entry.plural_index if entry.plural_index is not None else "",
            }
            if multi_file:
                row["source_file"] = entry.source_file or ""
            data.append(row)

        df = pd.DataFrame(data)

        # Reorder columns for multi-file mode
        if multi_file:
            columns = [
                "source_file", "msgid", "msgstr", "msgctxt",
                "extracted_comments", "translator_comments", "references",
                "fuzzy", "obsolete", "is_plural", "plural_index"
            ]
            df = df[columns]

        # Apply sorting if requested
        if sort_by:
            if sort_by not in df.columns:
                raise ValueError(f"Invalid sort field: {sort_by}")
            df = df.sort_values(by=sort_by)

    # Export to CSV
    if output_file:
        df.to_csv(output_file, index=False, encoding='utf-8')
    else:
        df.to_csv(sys.stdout, index=False, encoding='utf-8')
