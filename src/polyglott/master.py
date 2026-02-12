"""Master CSV management for consolidated translation workflow."""

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from polyglott.parser import POEntryData
from polyglott.context import match_context


# Reserved columns that POlyglott reads and writes
# All other columns are user-added and preserved verbatim
POLYGLOTT_COLUMNS = [
    'msgid',
    'msgstr',
    'status',
    'score',
    'context',
    'context_sources',
    'candidate',  # Stage 7: non-destructive machine translation
]


@dataclass
class MasterEntry:
    """Represents a single entry in the master CSV."""

    msgid: str
    msgstr: str
    status: str  # empty|machine|review|accepted|rejected|stale|conflict
    score: str  # "10" or "" (string for CSV compatibility)
    context: str
    context_sources: str
    candidate: str = ''  # Stage 7: machine translation suggestion
    # User-added columns (column sovereignty)
    extra_columns: Dict[str, str] = field(default_factory=dict)


def deduplicate_entries(po_entries: List[POEntryData]) -> Dict[str, POEntryData]:
    """Deduplicate PO entries by msgid, aggregating references and resolving conflicts.

    Deduplication key: msgid only (ignores msgctxt and plural_index).
    Conflict resolution: majority voting for msgstr.

    Args:
        po_entries: List of PO entries from one or more files

    Returns:
        Dictionary mapping msgid to deduplicated POEntryData
    """
    # Group entries by msgid
    groups: Dict[str, List[POEntryData]] = {}
    for entry in po_entries:
        # Skip empty msgid (PO file header)
        if not entry.msgid:
            continue
        if entry.msgid not in groups:
            groups[entry.msgid] = []
        groups[entry.msgid].append(entry)

    # Resolve each group
    result = {}
    for msgid, entries in groups.items():
        # Aggregate all references
        all_refs = []
        for entry in entries:
            if entry.references:
                all_refs.extend(entry.references.split())

        # Deduplicate and sort references
        unique_refs = sorted(set(all_refs))
        aggregated_refs = ' '.join(unique_refs)

        # Resolve msgstr conflict using majority voting
        resolved_msgstr = _resolve_msgstr_conflict(entries)

        # Use first entry as template, update with resolved data
        template = entries[0]
        result[msgid] = POEntryData(
            msgid=msgid,
            msgstr=resolved_msgstr,
            msgctxt=template.msgctxt,
            extracted_comments=template.extracted_comments,
            translator_comments=template.translator_comments,
            references=aggregated_refs,
            fuzzy=template.fuzzy,
            obsolete=template.obsolete,
            is_plural=template.is_plural,
            plural_index=template.plural_index,
            source_file=template.source_file
        )

    return result


def _resolve_msgstr_conflict(entries: List[POEntryData]) -> str:
    """Resolve msgstr conflicts using majority voting.

    Rules:
    1. Non-empty beats empty
    2. Most common msgstr wins
    3. Tie = first encountered

    Args:
        entries: List of entries with the same msgid

    Returns:
        Resolved msgstr
    """
    # Filter non-empty msgstr values
    non_empty = [e.msgstr for e in entries if e.msgstr]

    if not non_empty:
        # All empty, return empty
        return ''

    # Count occurrences
    counts = Counter(non_empty)
    most_common = counts.most_common(1)[0][0]

    return most_common


def _check_glossary_score(msgid: str, msgstr: str, glossary) -> str:
    """Check if translation matches glossary and return score.

    Args:
        msgid: Source text
        msgstr: Translation text
        glossary: Glossary instance (can be None)

    Returns:
        "10" if exact glossary match (case-insensitive), "" otherwise
    """
    if not glossary or not msgstr:
        return ""

    # Check if glossary has an exact match
    # Glossary.terms is already normalized to lowercase keys
    msgid_lower = msgid.lower()
    if msgid_lower in glossary.terms:
        expected_translation = glossary.terms[msgid_lower]
        # Case-insensitive comparison
        if msgstr.lower() == expected_translation.lower():
            return "10"

    return ""


def _compute_context(po_entry: POEntryData, context_rules: Optional[List[dict]]) -> tuple:
    """Compute context and context_sources for a PO entry.

    Args:
        po_entry: PO entry with references
        context_rules: Optional list of context rules

    Returns:
        Tuple of (context, context_sources)
    """
    if not context_rules:
        return ('', '')

    return match_context(po_entry.references, context_rules)


def create_master(
        po_entries: List[POEntryData],
        glossary=None,
        context_rules: Optional[List[dict]] = None
) -> List[MasterEntry]:
    """Create initial master CSV from PO entries.

    Args:
        po_entries: List of PO entries from one or more files
        glossary: Optional Glossary instance for scoring
        context_rules: Optional list of context rules

    Returns:
        List of MasterEntry objects sorted by msgid
    """
    # Deduplicate entries
    deduped = deduplicate_entries(po_entries)

    # Create master entries
    master_entries = []
    for msgid, po_entry in deduped.items():
        # Determine status
        if po_entry.msgstr:
            status = 'review'
        else:
            status = 'empty'

        # Compute score (only for review status)
        score = ''
        if status == 'review':
            score = _check_glossary_score(msgid, po_entry.msgstr, glossary)

        # Compute context
        context, context_sources = _compute_context(po_entry, context_rules)

        master_entries.append(MasterEntry(
            msgid=msgid,
            msgstr=po_entry.msgstr,
            status=status,
            score=score,
            context=context,
            context_sources=context_sources,
            candidate='',
            extra_columns={}
        ))

    # Sort by msgid for stable git diffs
    master_entries.sort(key=lambda e: e.msgid)

    return master_entries


def merge_master(
        existing: Dict[str, MasterEntry],
        po_entries: List[POEntryData],
        glossary=None,
        context_rules: Optional[List[dict]] = None
) -> List[MasterEntry]:
    """Merge existing master CSV with current PO file state.

    Implements 12+ status transition rules preserving human decisions.

    Args:
        existing: Dictionary of existing master entries (msgid -> MasterEntry)
        po_entries: List of current PO entries from files
        glossary: Optional Glossary instance for scoring
        context_rules: Optional list of context rules

    Returns:
        List of MasterEntry objects sorted by msgid
    """
    # Deduplicate current PO entries
    current = deduplicate_entries(po_entries)

    result = []

    # Process all msgids from both existing and current
    all_msgids = set(existing.keys()) | set(current.keys())

    for msgid in all_msgids:
        existing_entry = existing.get(msgid)
        current_entry = current.get(msgid)

        if existing_entry and current_entry:
            # Entry exists in both - apply merge rules
            merged = _apply_merge_rules(existing_entry, current_entry, glossary, context_rules)
            result.append(merged)
        elif existing_entry and not current_entry:
            # Entry missing from current PO files - handle stale
            stale = _handle_missing_entry(existing_entry)
            result.append(stale)
        elif not existing_entry and current_entry:
            # New entry - create fresh
            new_entry = _create_new_entry(current_entry, glossary, context_rules)
            result.append(new_entry)

    # Sort by msgid
    result.sort(key=lambda e: e.msgid)

    return result


def _apply_merge_rules(
        existing: MasterEntry,
        current_po: POEntryData,
        glossary,
        context_rules: Optional[List[dict]]
) -> MasterEntry:
    """Apply status transition rules when entry exists in both master and PO.

    Args:
        existing: Existing master entry
        current_po: Current PO entry
        glossary: Optional Glossary instance
        context_rules: Optional context rules

    Returns:
        Updated MasterEntry
    """
    # Always refresh context (derived data, not a human decision)
    context, context_sources = _compute_context(current_po, context_rules)

    status = existing.status
    msgstr = existing.msgstr
    score = existing.score  # Preserve by default

    if status == 'accepted':
        # Accepted: check if PO diverged
        if existing.msgstr == current_po.msgstr:
            # No change
            pass
        else:
            # Divergent - mark as conflict, preserve existing msgstr
            status = 'conflict'

    elif status == 'rejected':
        # Rejected: preserve as-is (no change even if PO updated)
        pass

    elif status == 'review':
        # Review: update msgstr from PO
        msgstr = current_po.msgstr

    elif status == 'machine':
        # Machine: update msgstr from PO
        msgstr = current_po.msgstr

    elif status == 'empty':
        # Empty: check if now has translation
        if current_po.msgstr:
            status = 'review'
            msgstr = current_po.msgstr
            # Assign score for new translation
            score = _check_glossary_score(existing.msgid, msgstr, glossary)
        # else: still empty, no change

    elif status == 'conflict':
        # Conflict: preserve as-is (manual resolution required)
        pass

    elif status == 'stale':
        # Stale reappears: transition to review
        status = 'review'
        msgstr = current_po.msgstr
        # Don't assign score on reappearance (not a new translation)

    return MasterEntry(
        msgid=existing.msgid,
        msgstr=msgstr,
        status=status,
        score=score,
        context=context,
        context_sources=context_sources,
        candidate=existing.candidate,  # Preserve candidate
        extra_columns=existing.extra_columns  # Preserve user columns
    )


def _handle_missing_entry(existing: MasterEntry) -> MasterEntry:
    """Handle entry that exists in master but missing from current PO files.

    Args:
        existing: Existing master entry

    Returns:
        Updated MasterEntry with stale status
    """
    # Transition to stale (except if already stale)
    if existing.status != 'stale':
        status = 'stale'
    else:
        status = 'stale'

    # Preserve all other fields
    return MasterEntry(
        msgid=existing.msgid,
        msgstr=existing.msgstr,
        status=status,
        score=existing.score,
        context=existing.context,
        context_sources=existing.context_sources,
        candidate=existing.candidate,  # Preserve candidate
        extra_columns=existing.extra_columns  # Preserve user columns
    )


def _create_new_entry(
        current_po: POEntryData,
        glossary,
        context_rules: Optional[List[dict]]
) -> MasterEntry:
    """Create master entry for new msgid appearing in PO files.

    Args:
        current_po: Current PO entry
        glossary: Optional Glossary instance
        context_rules: Optional context rules

    Returns:
        New MasterEntry
    """
    # Determine status
    if current_po.msgstr:
        status = 'review'
        score = _check_glossary_score(current_po.msgid, current_po.msgstr, glossary)
    else:
        status = 'empty'
        score = ''

    # Compute context
    context, context_sources = _compute_context(current_po, context_rules)

    return MasterEntry(
        msgid=current_po.msgid,
        msgstr=current_po.msgstr,
        status=status,
        score=score,
        context=context,
        context_sources=context_sources,
        candidate='',  # New entries have no candidate
        extra_columns={}  # New entries have no user columns
    )


def infer_language(master_csv_path: str, lang_override: Optional[str] = None) -> str:
    """Infer target language from master CSV filename.

    Language is inferred from the -<lang>.csv suffix:
    - master-de.csv → de
    - polyglott-accepted-de.csv → de
    - help-pages-de.csv → de
    - myproject-en-us.csv → en-us

    Args:
        master_csv_path: Path to master CSV file
        lang_override: Optional explicit language override

    Returns:
        Language code (e.g., 'de', 'en-us')

    Raises:
        ValueError: If language cannot be inferred and no override provided
    """
    # If explicit override, use it
    if lang_override:
        return lang_override

    # Extract filename
    filename = Path(master_csv_path).name

    # Must end with .csv
    if not filename.endswith('.csv'):
        raise ValueError(
            f"Cannot infer target language from '{filename}'.\n"
            f"Use a filename ending in '-<lang>.csv' (e.g., 'translations-de.csv')\n"
            f"or specify --lang explicitly."
        )

    # Remove .csv suffix
    stem = filename[:-4]

    # Try to match language patterns from the end
    # Language codes can be:
    # - Simple: de, en, fr (2-3 letters)
    # - Complex: en-us, pt-br, zh-hans (2-3 letters, hyphen, 2-4 letters)
    import re

    # Try complex pattern first (e.g., en-us, zh-hans)
    complex_match = re.search(r'-([a-z]{2,3}-[a-z]{2,4})$', stem)
    if complex_match:
        return complex_match.group(1)

    # Try simple pattern (e.g., de, fr)
    simple_match = re.search(r'-([a-z]{2,3})$', stem)
    if simple_match:
        return simple_match.group(1)

    # Special case: the entire filename is just the language code (e.g., de.csv)
    if re.match(r'^[a-z]{2,3}(-[a-z]{2,4})?$', stem):
        return stem

    raise ValueError(
        f"Cannot infer target language from '{filename}'.\n"
        f"Use a filename ending in '-<lang>.csv' (e.g., 'translations-de.csv')\n"
        f"or specify --lang explicitly."
    )


def load_master(path: str) -> Dict[str, MasterEntry]:
    """Load existing master CSV into dictionary with column sovereignty.

    POlyglott columns are loaded into MasterEntry fields.
    User-added columns are preserved in extra_columns dict.
    Missing POlyglott columns are added with empty defaults.

    Args:
        path: Path to master CSV file

    Returns:
        Dictionary mapping msgid to MasterEntry

    Raises:
        ValueError: If CSV is malformed or missing msgid column
    """
    master_path = Path(path)

    if not master_path.exists():
        return {}

    entries = {}

    try:
        with open(master_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)

            # Validate that msgid column exists (minimum requirement)
            if not reader.fieldnames or 'msgid' not in reader.fieldnames:
                raise ValueError(
                    f"Master CSV missing required 'msgid' column. "
                    f"Found columns: {reader.fieldnames}"
                )

            for row in reader:
                msgid = row['msgid']

                # Separate POlyglott columns from user columns
                extra_columns = {}
                for col_name, col_value in row.items():
                    if col_name not in POLYGLOTT_COLUMNS:
                        extra_columns[col_name] = col_value

                # Create entry with POlyglott columns (use empty string for missing)
                entries[msgid] = MasterEntry(
                    msgid=msgid,
                    msgstr=row.get('msgstr', ''),
                    status=row.get('status', ''),
                    score=row.get('score', ''),
                    context=row.get('context', ''),
                    context_sources=row.get('context_sources', ''),
                    candidate=row.get('candidate', ''),
                    extra_columns=extra_columns
                )

    except Exception as e:
        raise ValueError(f"Failed to load master CSV: {e}")

    return entries


def save_master(entries: List[MasterEntry], path: str) -> None:
    """Save master entries to CSV file with column sovereignty.

    POlyglott columns are written first (in POLYGLOTT_COLUMNS order).
    User columns are written after, maintaining their relative order.

    Args:
        entries: List of MasterEntry objects
        path: Path to output CSV file
    """
    master_path = Path(path)

    # Ensure parent directory exists
    master_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect all user column names across all entries (preserve order of first appearance)
    user_columns = []
    seen_cols = set()
    for entry in entries:
        for col_name in entry.extra_columns.keys():
            if col_name not in seen_cols:
                user_columns.append(col_name)
                seen_cols.add(col_name)

    # Build complete fieldnames: POlyglott columns first, then user columns
    fieldnames = POLYGLOTT_COLUMNS + user_columns

    with open(master_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)

        writer.writeheader()

        for entry in entries:
            # Start with POlyglott columns
            row = {
                'msgid': entry.msgid,
                'msgstr': entry.msgstr,
                'status': entry.status,
                'score': entry.score,
                'context': entry.context,
                'context_sources': entry.context_sources,
                'candidate': entry.candidate,
            }

            # Add user columns (empty string if entry doesn't have this column)
            for col_name in user_columns:
                row[col_name] = entry.extra_columns.get(col_name, '')

            writer.writerow(row)
