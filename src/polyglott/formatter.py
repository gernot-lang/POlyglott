"""Text output formatter for lint violations."""

import re
from collections import defaultdict
from typing import Dict, List

from polyglott.linter import Violation


def format_text_output(violations: List[Violation]) -> str:
    """Format violations as human-readable text.

    Args:
        violations: List of violations to format

    Returns:
        Formatted text output
    """
    if not violations:
        return "No issues found.\n"

    # Group violations by source file
    by_file: Dict[str, List[Violation]] = defaultdict(list)
    for violation in violations:
        source_file = violation.entry.source_file or "(unknown)"
        by_file[source_file].append(violation)

    # Build output
    lines = []
    total_errors = 0
    total_warnings = 0
    total_info = 0

    for source_file in sorted(by_file.keys()):
        file_violations = by_file[source_file]

        # File header
        lines.append(f"\n{source_file}:")
        lines.append("-" * len(f"{source_file}:"))

        for violation in file_violations:
            # Extract line number from references
            line_num = _extract_line_number(violation.entry.references)

            # Format: SEVERITY   line XX    check_name      message
            severity_str = violation.severity.value.upper().ljust(7)
            line_str = f"line {line_num}".ljust(10) if line_num else " " * 10
            check_str = violation.check_name.ljust(20)
            message_str = violation.message

            lines.append(f"  {severity_str} {line_str} {check_str} {message_str}")

            # Count by severity
            if violation.severity.value == "error":
                total_errors += 1
            elif violation.severity.value == "warning":
                total_warnings += 1
            else:
                total_info += 1

    # Summary
    lines.append("")
    lines.append("-" * 60)

    total_issues = total_errors + total_warnings + total_info
    num_files = len(by_file)

    summary_parts = []
    if total_errors > 0:
        summary_parts.append(f"{total_errors} error{'s' if total_errors != 1 else ''}")
    if total_warnings > 0:
        summary_parts.append(f"{total_warnings} warning{'s' if total_warnings != 1 else ''}")
    if total_info > 0:
        summary_parts.append(f"{total_info} info")

    summary = ", ".join(summary_parts)
    file_str = "file" if num_files == 1 else "files"

    lines.append(f"{summary} — {total_issues} issue{'s' if total_issues != 1 else ''} in {num_files} {file_str}")

    return "\n".join(lines) + "\n"


def _extract_line_number(references: str) -> str:
    """Extract first line number from references string.

    Args:
        references: Space-separated "file:line" references

    Returns:
        Line number as string, or empty string if not found
    """
    if not references:
        return ""

    # Split by space and take first reference
    refs = references.split()
    if not refs:
        return ""

    # Extract line number from "file:line" format
    match = re.search(r':(\d+)$', refs[0])
    if match:
        return match.group(1)

    return ""
