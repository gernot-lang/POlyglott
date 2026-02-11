"""CSV exporter for PO file data."""

import sys
from typing import List, Optional, TextIO

import pandas as pd

from polyglott.parser import POEntryData


def export_to_csv(
        entries: List[POEntryData],
        output_file: Optional[str] = None,
        sort_by: Optional[str] = None,
        multi_file: bool = False,
        lint_mode: bool = False,
        violations: Optional[List] = None,
        context_data: Optional[dict] = None
) -> None:
    """Export PO entries to CSV format.

    Args:
        entries: List of POEntryData objects to export
        output_file: Output file path (None for stdout)
        sort_by: Optional field name to sort by
        multi_file: Whether to include source_file column
        lint_mode: Whether to export in lint mode (with violations)
        violations: List of Violation objects (required if lint_mode=True)
        context_data: Optional dict mapping entry keys to (context, context_sources) tuples

    Raises:
        ValueError: If sort_by field doesn't exist or lint_mode without violations
    """
    if lint_mode and violations is None:
        raise ValueError("violations required when lint_mode=True")
    if lint_mode:
        # Lint mode: export violations
        df = _export_violations_csv(violations, multi_file, context_data)
    else:
        # Normal mode: export entries
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
            # Add context columns if context_data is provided
            if context_data is not None:
                columns.extend(["context", "context_sources"])
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

                # Add context columns if context_data is provided
                if context_data is not None:
                    entry_key = (entry.msgid, entry.msgctxt, entry.plural_index)
                    context, context_sources = context_data.get(entry_key, ('', ''))
                    row["context"] = context
                    row["context_sources"] = context_sources

                data.append(row)

            df = pd.DataFrame(data)

            # Reorder columns for multi-file mode
            if multi_file:
                columns = [
                    "source_file", "msgid", "msgstr", "msgctxt",
                    "extracted_comments", "translator_comments", "references",
                    "fuzzy", "obsolete", "is_plural", "plural_index"
                ]
                if context_data is not None:
                    columns.extend(["context", "context_sources"])
                df = df[columns]
            elif context_data is not None:
                # Single file mode with context - reorder to add context columns at end
                columns = [
                    "msgid", "msgstr", "msgctxt",
                    "extracted_comments", "translator_comments", "references",
                    "fuzzy", "obsolete", "is_plural", "plural_index",
                    "context", "context_sources"
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


def _export_violations_csv(
        violations: List,
        multi_file: bool,
        context_data: Optional[dict] = None
) -> pd.DataFrame:
    """Export violations to a DataFrame.

    Args:
        violations: List of Violation objects
        multi_file: Whether to include source_file column
        context_data: Optional dict mapping entry keys to (context, context_sources) tuples

    Returns:
        DataFrame with violation data
    """
    if not violations:
        # Empty violations - return empty DataFrame with headers
        if multi_file:
            columns = [
                "source_file", "msgid", "msgstr", "msgctxt",
                "extracted_comments", "translator_comments", "references",
                "fuzzy", "obsolete", "is_plural", "plural_index",
                "severity", "check", "message"
            ]
        else:
            columns = [
                "msgid", "msgstr", "msgctxt",
                "extracted_comments", "translator_comments", "references",
                "fuzzy", "obsolete", "is_plural", "plural_index",
                "severity", "check", "message"
            ]
        # Add context columns if context_data is provided
        if context_data is not None:
            columns.extend(["context", "context_sources"])
        return pd.DataFrame(columns=columns)

    # Convert violations to rows
    data = []
    for i, violation in enumerate(violations):
        entry = violation.entry
        try:
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
                "severity": violation.severity.value,
                "check": violation.check_name,
                "message": violation.message,
            }
            if multi_file:
                row["source_file"] = entry.source_file or ""

            # Add context columns if context_data is provided
            if context_data is not None:
                entry_key = (entry.msgid, entry.msgctxt, entry.plural_index)
                context, context_sources = context_data.get(entry_key, ('', ''))
                row["context"] = context
                row["context_sources"] = context_sources

            data.append(row)
        except AttributeError as e:
            # Better error message for debugging
            raise ValueError(
                f"Error processing violation {i} (msgid: {getattr(entry, 'msgid', 'unknown')}): {e}. "
                f"Check if entry fields have unexpected types (e.g., lists instead of strings)."
            ) from e

    try:
        df = pd.DataFrame(data)
    except Exception as e:
        # Provide helpful error for DataFrame creation issues
        raise ValueError(
            f"Error creating DataFrame from violations: {e}. "
            f"This may indicate unexpected data types in violation entries. "
            f"Total violations: {len(violations)}, data rows: {len(data)}"
        ) from e

    # Reorder columns
    if multi_file:
        columns = [
            "source_file", "msgid", "msgstr", "msgctxt",
            "extracted_comments", "translator_comments", "references",
            "fuzzy", "obsolete", "is_plural", "plural_index",
            "severity", "check", "message"
        ]
    else:
        columns = [
            "msgid", "msgstr", "msgctxt",
            "extracted_comments", "translator_comments", "references",
            "fuzzy", "obsolete", "is_plural", "plural_index",
            "severity", "check", "message"
        ]

    # Add context columns if context_data is provided
    if context_data is not None:
        columns.extend(["context", "context_sources"])

    return df[columns]
