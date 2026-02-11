"""Command-line interface for POlyglott."""

import argparse
import glob
import os
import sys
from pathlib import Path
from typing import List, Optional

from polyglott import __version__
from polyglott.parser import POParser, MultiPOParser
from polyglott.exporter import export_to_csv


def discover_po_files(
    include_patterns: List[str],
    exclude_patterns: Optional[List[str]] = None
) -> List[str]:
    """Discover PO files using glob patterns.

    Args:
        include_patterns: List of glob patterns to include
        exclude_patterns: Optional list of patterns to exclude

    Returns:
        List of file paths matching the patterns
    """
    files = set()

    for pattern in include_patterns:
        # Expand user home directory
        expanded = os.path.expanduser(pattern)
        # Find matching files
        matches = glob.glob(expanded, recursive=True)
        files.update(matches)

    # Apply exclusions
    if exclude_patterns:
        excluded = set()
        for pattern in exclude_patterns:
            expanded = os.path.expanduser(pattern)
            matches = glob.glob(expanded, recursive=True)
            excluded.update(matches)
        files -= excluded

    return sorted(files)


def cmd_scan(args: argparse.Namespace) -> int:
    """Execute the scan subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Determine input files
        if args.file and args.include:
            print("Error: Cannot specify both FILE and --include", file=sys.stderr)
            return 1

        if args.file:
            # Single file mode
            filepath = args.file
            if not os.path.exists(filepath):
                print(f"Error: File not found: {filepath}", file=sys.stderr)
                return 1

            parser = POParser(filepath)
            entries = parser.parse()
            stats = parser.get_statistics()
            multi_file = False

        elif args.include:
            # Multi-file mode with glob patterns
            files = discover_po_files(args.include, args.exclude)

            if not files:
                print("Error: No PO files found matching patterns", file=sys.stderr)
                return 1

            # Validate all files exist
            for filepath in files:
                if not os.path.exists(filepath):
                    print(f"Error: File not found: {filepath}", file=sys.stderr)
                    return 1

            parser = MultiPOParser(files)
            entries = parser.parse()
            stats = parser.get_combined_statistics()
            multi_file = True

        else:
            print("Error: Must specify either FILE or --include", file=sys.stderr)
            return 1

        # Export to CSV
        export_to_csv(
            entries,
            output_file=args.output,
            sort_by=args.sort_by,
            multi_file=multi_file
        )

        # Print statistics to stderr (keeps stdout clean for CSV)
        print(f"\nStatistics:", file=sys.stderr)
        print(f"  Total entries: {stats.total}", file=sys.stderr)
        print(f"  Untranslated: {stats.untranslated}", file=sys.stderr)
        print(f"  Fuzzy: {stats.fuzzy}", file=sys.stderr)
        print(f"  Plurals: {stats.plurals}", file=sys.stderr)

        if multi_file:
            print(f"  Files processed: {len(files)}", file=sys.stderr)

        return 0

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point for the CLI.

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        prog="polyglott",
        description="Parse gettext PO files and export to CSV for translation workflow management"
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Scan subcommand
    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan PO file(s) and export to CSV"
    )

    scan_parser.add_argument(
        "file",
        nargs="?",
        help="Path to a single PO file"
    )

    scan_parser.add_argument(
        "-o", "--output",
        help="Output CSV file (default: stdout)"
    )

    scan_parser.add_argument(
        "--include",
        action="append",
        help="Glob pattern(s) for PO files (repeatable, e.g., '**/*.po')"
    )

    scan_parser.add_argument(
        "--exclude",
        action="append",
        help="Exclude pattern(s) (repeatable)"
    )

    scan_parser.add_argument(
        "--sort-by",
        choices=["msgid", "source_file", "fuzzy", "msgstr"],
        help="Sort output by field"
    )

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    if args.command == "scan":
        return cmd_scan(args)
    elif args.command is None:
        parser.print_help()
        return 1
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
