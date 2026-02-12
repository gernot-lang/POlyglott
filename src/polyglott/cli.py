"""Command-line interface for POlyglott."""

import argparse
import glob
import os
import sys
from collections import Counter
from pathlib import Path
from typing import List, Optional

from polyglott import __version__
from polyglott.parser import POParser, MultiPOParser
from polyglott.exporter import export_to_csv
from polyglott.linter import Glossary, Severity, run_checks
from polyglott.formatter import format_text_output
from polyglott.context import load_context_rules, load_preset, match_context


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


def load_context_rules_from_args(args: argparse.Namespace) -> Optional[List[dict]]:
    """Load context rules from CLI arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        List of context rules or None if no context flags provided

    Raises:
        ValueError: If both context_rules and preset are provided
        FileNotFoundError: If rules file doesn't exist
    """
    has_context_rules = hasattr(args, 'context_rules') and args.context_rules
    has_preset = hasattr(args, 'preset') and args.preset

    # Check mutual exclusivity
    if has_context_rules and has_preset:
        raise ValueError("Cannot specify both --context-rules and --preset")

    if has_context_rules:
        return load_context_rules(args.context_rules)
    elif has_preset:
        return load_preset(args.preset)
    else:
        return None


def cmd_lint(args: argparse.Namespace) -> int:
    """Execute the lint subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0=clean, 1=errors, 2=warnings only)
    """
    try:
        # Load context rules if specified
        try:
            context_rules = load_context_rules_from_args(args)
        except (ValueError, FileNotFoundError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

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
            # Set source_file for single file mode too (for text output)
            source_file = Path(filepath).name
            entries = parser.parse(source_file=source_file)
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
            multi_file = True

        else:
            print("Error: Must specify either FILE or --include", file=sys.stderr)
            return 1

        # Load glossary if specified
        glossary = None
        if args.glossary:
            try:
                glossary = Glossary(args.glossary)
            except (FileNotFoundError, ValueError) as e:
                print(f"Error loading glossary: {e}", file=sys.stderr)
                return 1

        # Run checks
        violations = run_checks(
            entries,
            glossary=glossary,
            include_checks=args.check,
            exclude_checks=args.no_check
        )

        # Filter by severity
        severity_order = {"error": 3, "warning": 2, "info": 1}
        min_severity = severity_order[args.severity]
        violations = [
            v for v in violations
            if severity_order[v.severity.value] >= min_severity
        ]

        # Compute context for each entry if rules are provided
        context_data = None
        if context_rules:
            context_data = {}
            for entry in entries:
                context, context_sources = match_context(entry.references, context_rules)
                entry_key = (entry.msgid, entry.msgctxt, entry.plural_index)
                context_data[entry_key] = (context, context_sources)

        # Output results
        if args.format == "text":
            output = format_text_output(violations)
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(output)
            else:
                print(output, end='')
        else:  # CSV format
            export_to_csv(
                entries,
                output_file=args.output,
                multi_file=multi_file,
                lint_mode=True,
                violations=violations,
                context_data=context_data
            )

        # Determine exit code
        if not violations:
            return 0

        has_errors = any(v.severity == Severity.ERROR for v in violations)
        if has_errors:
            return 1

        return 2  # Warnings or info only

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def cmd_scan(args: argparse.Namespace) -> int:
    """Execute the scan subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Load context rules if specified
        try:
            context_rules = load_context_rules_from_args(args)
        except (ValueError, FileNotFoundError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        # Single file mode only (Stage 3 behavior)
        if not args.file:
            print("Error: Must specify FILE", file=sys.stderr)
            return 1

        filepath = args.file
        if not os.path.exists(filepath):
            print(f"Error: File not found: {filepath}", file=sys.stderr)
            return 1

        parser = POParser(filepath)
        entries = parser.parse()
        stats = parser.get_statistics()

        # Compute context for each entry if rules are provided
        context_data = None
        if context_rules:
            context_data = {}
            for entry in entries:
                context, context_sources = match_context(entry.references, context_rules)
                entry_key = (entry.msgid, entry.msgctxt, entry.plural_index)
                context_data[entry_key] = (context, context_sources)

        # Export to CSV
        export_to_csv(
            entries,
            output_file=args.output,
            sort_by=args.sort_by,
            multi_file=False,
            context_data=context_data
        )

        # Print statistics to stderr (keeps stdout clean for CSV)
        print(f"\nStatistics:", file=sys.stderr)
        print(f"  Total entries: {stats.total}", file=sys.stderr)
        print(f"  Untranslated: {stats.untranslated}", file=sys.stderr)
        print(f"  Fuzzy: {stats.fuzzy}", file=sys.stderr)
        print(f"  Plurals: {stats.plurals}", file=sys.stderr)

        return 0

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def cmd_import(args: argparse.Namespace) -> int:
    """Execute the import subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        from polyglott.master import (
            load_master, save_master, create_master, merge_master, infer_language
        )

        # Validate language
        try:
            lang = infer_language(args.master_csv, args.lang if hasattr(args, 'lang') else None)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        # Load context rules if specified
        try:
            context_rules = load_context_rules_from_args(args)
        except (ValueError, FileNotFoundError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        # Discover PO files
        if not args.po_files:
            print("Error: Must specify at least one PO file", file=sys.stderr)
            return 1

        files = discover_po_files(args.po_files, args.exclude if hasattr(args, 'exclude') else None)

        if not files:
            print("Error: No PO files found matching patterns", file=sys.stderr)
            return 1

        # Validate all files exist
        for filepath in files:
            if not os.path.exists(filepath):
                print(f"Error: File not found: {filepath}", file=sys.stderr)
                return 1

        # Parse all PO files
        parser = MultiPOParser(files)
        entries = parser.parse()

        # Load glossary if provided
        glossary = None
        if hasattr(args, 'glossary') and args.glossary:
            try:
                from polyglott.linter import Glossary
                glossary = Glossary(args.glossary)
            except (FileNotFoundError, ValueError) as e:
                print(f"Error loading glossary: {e}", file=sys.stderr)
                return 1

        # Check if master exists
        if Path(args.master_csv).exists():
            existing = load_master(args.master_csv)
            result = merge_master(existing, entries, glossary, context_rules)
        else:
            result = create_master(entries, glossary, context_rules)

        # Save master CSV
        save_master(result, args.master_csv)

        # Print statistics to stderr
        print(f"\nMaster CSV: {args.master_csv}", file=sys.stderr)
        print(f"  Language: {lang}", file=sys.stderr)
        print(f"  Total entries: {len(result)}", file=sys.stderr)

        status_counts = Counter(e.status for e in result)
        for status in sorted(status_counts.keys()):
            print(f"  {status}: {status_counts[status]}", file=sys.stderr)

        return 0

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def cmd_export(args: argparse.Namespace) -> int:
    """Execute the export subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        from polyglott.master import load_master, infer_language
        from polyglott.po_writer import export_to_po

        # Validate language (for informational purposes)
        try:
            lang = infer_language(args.master_csv, args.lang if hasattr(args, 'lang') else None)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        # Load master CSV
        if not Path(args.master_csv).exists():
            print(f"Error: Master CSV not found: {args.master_csv}", file=sys.stderr)
            return 1

        master_dict = load_master(args.master_csv)
        master_entries = list(master_dict.values())

        # Discover PO files
        if not args.po_files:
            print("Error: Must specify at least one PO file", file=sys.stderr)
            return 1

        files = discover_po_files(args.po_files, args.exclude if hasattr(args, 'exclude') else None)

        if not files:
            print("Error: No PO files found matching patterns", file=sys.stderr)
            return 1

        # Validate all files exist
        for filepath in files:
            if not os.path.exists(filepath):
                print(f"Error: File not found: {filepath}", file=sys.stderr)
                return 1

        # Determine which statuses to export
        statuses = set(args.status) if hasattr(args, 'status') and args.status else {'accepted'}

        # Dry run flag
        dry_run = args.dry_run if hasattr(args, 'dry_run') else False

        # Verbose flag
        verbose = args.verbose if hasattr(args, 'verbose') else False

        # Export to each PO file
        total_writes = 0
        total_overwrites = 0
        file_results = []

        for po_file in files:
            result = export_to_po(
                master_entries,
                po_file,
                statuses,
                dry_run=dry_run,
                verbose=verbose
            )

            total_writes += result.writes
            total_overwrites += result.overwrites
            file_results.append((po_file, result))

        # Print verbose details if requested
        if verbose:
            for po_file, result in file_results:
                for detail in result.details:
                    print(detail)
            if file_results:
                print()  # Blank line before summary

        # Print summary
        if dry_run:
            print("Dry run — no files will be modified.\n")
            prefix = "Would update"
        else:
            prefix = "Updated"

        total_updated = total_writes + total_overwrites
        print(f"{prefix} {total_updated} entries across {len(files)} files ({total_overwrites} overwrites)")

        for po_file, result in file_results:
            updates = result.writes + result.overwrites
            if updates > 0:
                print(f"  {po_file}: {updates} writes, {result.overwrites} overwrites")

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
        help="Scan PO file and export to CSV"
    )

    scan_parser.add_argument(
        "file",
        help="Path to a single PO file"
    )

    scan_parser.add_argument(
        "-o", "--output",
        help="Output CSV file (default: stdout)"
    )

    scan_parser.add_argument(
        "--sort-by",
        choices=["msgid", "source_file", "fuzzy", "msgstr"],
        help="Sort output by field"
    )

    scan_parser.add_argument(
        "--context-rules",
        help="Path to YAML context rules file"
    )

    scan_parser.add_argument(
        "--preset",
        help="Use built-in context preset (e.g., 'django')"
    )

    scan_parser.add_argument(
        "--glossary",
        help="Path to YAML glossary file"
    )

    # Import subcommand
    import_parser = subparsers.add_parser(
        "import",
        help="Import PO file translations into master CSV"
    )

    import_parser.add_argument(
        "master_csv",
        help="Path to master CSV file (*-<lang>.csv)"
    )

    import_parser.add_argument(
        "po_files",
        nargs="+",
        help="One or more PO files or glob patterns"
    )

    import_parser.add_argument(
        "--glossary",
        help="Path to YAML glossary file (for auto-scoring)"
    )

    import_parser.add_argument(
        "--context-rules",
        help="Path to YAML context rules file"
    )

    import_parser.add_argument(
        "--preset",
        help="Use built-in context preset (e.g., 'django')"
    )

    import_parser.add_argument(
        "--lang",
        help="Override target language (instead of inferring from filename)"
    )

    import_parser.add_argument(
        "--exclude",
        action="append",
        help="Exclude pattern(s) (repeatable)"
    )

    # Export subcommand
    export_parser = subparsers.add_parser(
        "export",
        help="Export master CSV translations back to PO files"
    )

    export_parser.add_argument(
        "master_csv",
        help="Path to master CSV file (*-<lang>.csv)"
    )

    export_parser.add_argument(
        "po_files",
        nargs="+",
        help="One or more PO files or glob patterns"
    )

    export_parser.add_argument(
        "--status",
        action="append",
        default=None,
        help="Which statuses to export (repeatable, default: accepted)"
    )

    export_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without modifying PO files"
    )

    export_parser.add_argument(
        "--lang",
        help="Override target language (instead of inferring from filename)"
    )

    export_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show per-entry detail"
    )

    export_parser.add_argument(
        "--exclude",
        action="append",
        help="Exclude pattern(s) (repeatable)"
    )

    # Lint subcommand
    lint_parser = subparsers.add_parser(
        "lint",
        help="Check PO file(s) for quality issues"
    )

    lint_parser.add_argument(
        "file",
        nargs="?",
        help="Path to a single PO file"
    )

    lint_parser.add_argument(
        "-o", "--output",
        help="Output file (default: stdout)"
    )

    lint_parser.add_argument(
        "--include",
        action="append",
        help="Glob pattern(s) for PO files (repeatable, e.g., '**/*.po')"
    )

    lint_parser.add_argument(
        "--exclude",
        action="append",
        help="Exclude pattern(s) (repeatable)"
    )

    lint_parser.add_argument(
        "--glossary",
        help="Path to YAML glossary file"
    )

    lint_parser.add_argument(
        "--format",
        choices=["csv", "text"],
        default="csv",
        help="Output format (default: csv)"
    )

    lint_parser.add_argument(
        "--severity",
        choices=["error", "warning", "info"],
        default="info",
        help="Minimum severity to report (default: info)"
    )

    lint_parser.add_argument(
        "--check",
        action="append",
        dest="check",
        help="Include only specified check(s) (repeatable)"
    )

    lint_parser.add_argument(
        "--no-check",
        action="append",
        dest="no_check",
        help="Exclude specified check(s) (repeatable)"
    )

    lint_parser.add_argument(
        "--context-rules",
        help="Path to YAML context rules file"
    )

    lint_parser.add_argument(
        "--preset",
        help="Use built-in context preset (e.g., 'django')"
    )

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    if args.command == "scan":
        return cmd_scan(args)
    elif args.command == "lint":
        return cmd_lint(args)
    elif args.command == "import":
        return cmd_import(args)
    elif args.command == "export":
        return cmd_export(args)
    elif args.command is None:
        parser.print_help()
        return 1
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
