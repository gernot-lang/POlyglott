"""Write master CSV translations back to PO files."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

import polib

from polyglott.master import MasterEntry


@dataclass
class ExportResult:
    """Result of exporting master CSV to PO files."""

    writes: int  # New translations written
    overwrites: int  # Existing translations overwritten
    skips: int  # Entries skipped (not in master or wrong status)
    details: List[str]  # Per-entry detail messages (for verbose mode)


def export_to_po(
        master_entries: List[MasterEntry],
        po_path: str,
        statuses: Set[str],
        dry_run: bool = False,
        verbose: bool = False
) -> ExportResult:
    """Export master CSV translations to a PO file.

    Args:
        master_entries: List of master entries
        po_path: Path to PO file to update
        statuses: Set of statuses to export (e.g., {'accepted', 'machine'})
        dry_run: If True, don't modify files
        verbose: If True, generate per-entry detail messages

    Returns:
        ExportResult with statistics and optional details
    """
    # Load PO file
    po = polib.pofile(po_path)

    # Build master lookup: msgid -> MasterEntry
    master_lookup: Dict[str, MasterEntry] = {
        entry.msgid: entry for entry in master_entries
    }

    writes = 0
    overwrites = 0
    skips = 0
    details = []

    # Process each PO entry
    for po_entry in po:
        msgid = po_entry.msgid

        # Skip if not in master
        if msgid not in master_lookup:
            if verbose:
                details.append(f"SKIP     {po_path}: \"{msgid}\" — not in master")
            skips += 1
            continue

        master_entry = master_lookup[msgid]

        # Skip if status doesn't match filter
        if master_entry.status not in statuses:
            if verbose:
                details.append(
                    f"SKIP     {po_path}: \"{msgid}\" — status {master_entry.status} not in {statuses}"
                )
            skips += 1
            continue

        # Skip if master has empty msgstr
        if not master_entry.msgstr:
            if verbose:
                details.append(f"SKIP     {po_path}: \"{msgid}\" — empty msgstr in master")
            skips += 1
            continue

        # Determine action: write, overwrite, or skip
        if not po_entry.msgstr:
            action = "write"
        elif po_entry.msgstr != master_entry.msgstr:
            action = "overwrite"
        else:
            action = "skip"  # PO already matches master

        # Skip if already matches (no need to write)
        if action == "skip":
            skips += 1
            if verbose:
                details.append(f"SKIP     {po_path}: \"{msgid}\" — already matches master")
            continue

        # Update msgstr
        old_msgstr = po_entry.msgstr
        po_entry.msgstr = master_entry.msgstr

        # Handle fuzzy flag based on status
        if master_entry.status == 'accepted':
            # Clear fuzzy flag (translation is human-approved)
            if 'fuzzy' in po_entry.flags:
                po_entry.flags.remove('fuzzy')
        elif master_entry.status == 'machine':
            # Set fuzzy flag (translation needs review)
            if 'fuzzy' not in po_entry.flags:
                po_entry.flags.append('fuzzy')
        # For 'review' status: leave fuzzy flag unchanged

        # Record action
        if action == "overwrite":
            overwrites += 1
            if verbose:
                details.append(
                    f"OVERWRITE {po_path}: \"{msgid}\" — \"{old_msgstr}\" → \"{master_entry.msgstr}\""
                )
        else:  # action == "write"
            writes += 1
            if verbose:
                details.append(
                    f"WRITE    {po_path}: \"{msgid}\" → \"{master_entry.msgstr}\""
                )

    # Save PO file (unless dry run)
    if not dry_run:
        po.save(po_path)

    return ExportResult(
        writes=writes,
        overwrites=overwrites,
        skips=skips,
        details=details
    )
