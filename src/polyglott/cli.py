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


def resolve_po_files(
        positional_files: Optional[List[str]] = None,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None
) -> List[str]:
    """Collect PO files from positional args and --include, minus --exclude.

    Args:
        positional_files: Files passed as positional arguments (already shell-expanded)
        include_patterns: List of glob patterns to include (--include flags)
        exclude_patterns: List of glob patterns to exclude (--exclude flags)

    Returns:
        Sorted list of unique file paths

    Raises:
        ValueError: If no files result from any source
    """
    files = set()

    # 1. Add positional files (already shell-expanded)
    if positional_files:
        files.update(positional_files)

    # 2. Expand each --include pattern via glob (recursive=True)
    if include_patterns:
        for pattern in include_patterns:
            expanded = os.path.expanduser(pattern)
            matches = glob.glob(expanded, recursive=True)
            if not matches:
                print(f"Warning: Pattern '{pattern}' matched no files.", file=sys.stderr)
            files.update(matches)

    # 3. Raise error if no files from any source
    if not files:
        raise ValueError("No PO files specified. Use positional arguments or --include.")

    # 4. Remove files matching any --exclude pattern
    if exclude_patterns:
        excluded = set()
        for pattern in exclude_patterns:
            expanded = os.path.expanduser(pattern)
            matches = glob.glob(expanded, recursive=True)
            excluded.update(matches)
        files -= excluded

    # 5. Raise error if all files were excluded
    if not files:
        raise ValueError("No PO files remain after applying --exclude patterns.")

    # 6. Return sorted list of paths
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
            try:
                files = resolve_po_files(
                    positional_files=None,
                    include_patterns=args.include,
                    exclude_patterns=args.exclude
                )
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
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
            lang = infer_language(args.master, args.lang if hasattr(args, 'lang') else None)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        # Load context rules if specified
        try:
            context_rules = load_context_rules_from_args(args)
        except (ValueError, FileNotFoundError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        # Resolve PO files from positional + --include - --exclude
        try:
            files = resolve_po_files(
                positional_files=args.po_files if args.po_files else None,
                include_patterns=args.include if hasattr(args, 'include') and args.include else None,
                exclude_patterns=args.exclude if hasattr(args, 'exclude') and args.exclude else None
            )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
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
        if Path(args.master).exists():
            existing = load_master(args.master)
            result = merge_master(existing, entries, glossary, context_rules)
        else:
            result = create_master(entries, glossary, context_rules)

        # Save master CSV
        save_master(result, args.master)

        # Print statistics to stderr
        print(f"\nMaster CSV: {args.master}", file=sys.stderr)
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
            lang = infer_language(args.master, args.lang if hasattr(args, 'lang') else None)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        # Load master CSV
        if not Path(args.master).exists():
            print(f"Error: Master CSV not found: {args.master}", file=sys.stderr)
            return 1

        master_dict = load_master(args.master)
        master_entries = list(master_dict.values())

        # Resolve PO files from positional + --include - --exclude
        try:
            files = resolve_po_files(
                positional_files=args.po_files if args.po_files else None,
                include_patterns=args.include if hasattr(args, 'include') and args.include else None,
                exclude_patterns=args.exclude if hasattr(args, 'exclude') and args.exclude else None
            )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
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


def cmd_translate(args: argparse.Namespace) -> int:
    """Execute the translate subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        from polyglott.master import load_master, save_master, infer_language, MasterEntry
        from polyglott.translate import DeepLBackend, TranslationError

        # Validate language
        try:
            lang = infer_language(args.master, args.lang if hasattr(args, 'lang') else None)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        # Load master CSV
        if not Path(args.master).exists():
            print(f"Error: Master CSV not found: {args.master}", file=sys.stderr)
            return 1

        master_dict = load_master(args.master)
        master_entries = list(master_dict.values())

        # Filter by status (default: empty)
        statuses = set(args.status) if hasattr(args, 'status') and args.status else {'empty'}
        entries_to_translate = [e for e in master_entries if e.status in statuses]

        if not entries_to_translate:
            print(f"No entries with status {', '.join(sorted(statuses))} found.", file=sys.stderr)
            return 0

        # Get auth key from args or environment
        auth_key = args.auth_key if hasattr(args, 'auth_key') and args.auth_key else os.environ.get('DEEPL_AUTH_KEY')
        if not auth_key:
            print("Error: DeepL API key required. Use --auth-key or set DEEPL_AUTH_KEY environment variable.", file=sys.stderr)
            return 1

        # Dry run mode: estimate cost without API calls
        if args.dry_run if hasattr(args, 'dry_run') else False:
            return _dry_run_translate(entries_to_translate, lang)

        # Initialize DeepL backend
        try:
            backend = DeepLBackend(auth_key)
        except TranslationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        # Load glossary if provided
        glossary_terms = None
        if hasattr(args, 'glossary') and args.glossary:
            try:
                from polyglott.linter import Glossary
                glossary = Glossary(args.glossary)
                glossary_terms = glossary.terms
            except (FileNotFoundError, ValueError) as e:
                print(f"Warning: Failed to load glossary: {e}", file=sys.stderr)
                print("Continuing without glossary protection.", file=sys.stderr)

        # Create ephemeral glossary if terms available
        if glossary_terms:
            # Infer source language (assume English for now)
            source_lang = 'en'
            backend.create_glossary(glossary_terms, source_lang, lang)

        # Translate entries
        translated_count = 0
        passthrough_count = 0
        error_count = 0

        try:
            for entry in entries_to_translate:
                try:
                    # Translate msgid to msgstr
                    msgstr = backend.translate_entry(
                        entry.msgid,
                        source_lang='en',  # Assume English source
                        target_lang=lang,
                        context=entry.context if hasattr(entry, 'context') else None,
                        glossary_entries=glossary_terms
                    )

                    # Update entry
                    entry.msgstr = msgstr
                    entry.status = 'machine'
                    entry.score = ''  # Clear score for machine translations

                    # Check if passthrough (msgstr == msgid)
                    if msgstr == entry.msgid:
                        passthrough_count += 1
                    else:
                        translated_count += 1

                except TranslationError as e:
                    print(f"Warning: Failed to translate '{entry.msgid[:50]}...': {e}", file=sys.stderr)
                    error_count += 1
                    continue

        finally:
            # Always save progress and cleanup
            save_master(master_entries, args.master)
            backend.delete_glossary()

        # Print summary
        total_processed = translated_count + passthrough_count
        print(f"\nTranslation complete:", file=sys.stderr)
        print(f"  Entries translated: {translated_count}", file=sys.stderr)
        print(f"  Passthrough entries: {passthrough_count}", file=sys.stderr)
        if error_count > 0:
            print(f"  Errors: {error_count}", file=sys.stderr)
        print(f"  Master CSV updated: {args.master}", file=sys.stderr)

        return 0

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def _dry_run_translate(entries: List, lang: str) -> int:
    """
    Dry-run mode: estimate translation cost without API calls.

    Args:
        entries: List of MasterEntry objects to translate
        lang: Target language code

    Returns:
        Exit code (0 for success)
    """
    from polyglott.translate import DeepLBackend

    # Estimate character count
    msgids = [e.msgid for e in entries]

    # Create a temporary backend instance just for estimation (no API key needed)
    # We'll just calculate manually instead
    total_chars = sum(len(msgid) for msgid in msgids)

    print(f"Dry run — no API calls will be made.\n", file=sys.stderr)
    print(f"Entries to translate: {len(entries)}", file=sys.stderr)
    print(f"Estimated characters: {total_chars:,}", file=sys.stderr)
    print(f"Target language: {lang}", file=sys.stderr)
    print(f"\nNote: DeepL pricing is based on source text character count.", file=sys.stderr)
    print(f"See https://www.deepl.com/pro-api for current rates.", file=sys.stderr)

    return 0


def main() -> int:
    """Main entry point for the CLI.

    Returns:
        Exit code
    """
    # Create parent parsers for shared arguments

    # PO file input — used by scan, import, export, lint
    po_input_parser = argparse.ArgumentParser(add_help=False)
    po_input_parser.add_argument(
        'po_files',
        nargs='*',
        help='PO files (positional, shell-expanded)'
    )
    po_input_parser.add_argument(
        '--include',
        action='append',
        help='Glob pattern for PO files (repeatable, e.g., "**/*.po")'
    )
    po_input_parser.add_argument(
        '--exclude',
        action='append',
        help='Glob pattern to exclude (repeatable)'
    )

    # Sort control — used by scan, import, export
    sort_parser = argparse.ArgumentParser(add_help=False)
    sort_parser.add_argument(
        '--sort-by',
        choices=['msgid', 'source_file', 'fuzzy', 'msgstr'],
        help='Sort order for output'
    )

    # Glossary — used by scan, import, lint
    glossary_parser = argparse.ArgumentParser(add_help=False)
    glossary_parser.add_argument(
        '--glossary',
        help='Path to YAML glossary file'
    )

    # Context — used by scan, import
    context_parser = argparse.ArgumentParser(add_help=False)
    context_parser.add_argument(
        '--context-rules',
        help='Path to YAML context rules file'
    )
    context_parser.add_argument(
        '--preset',
        help='Use built-in context preset (e.g., "django")'
    )

    # Master CSV — used by import, export
    master_parser = argparse.ArgumentParser(add_help=False)
    master_parser.add_argument(
        '--master',
        required=True,
        help='Path to master CSV file (*-<lang>.csv)'
    )

    # Language — used by import, export
    lang_parser = argparse.ArgumentParser(add_help=False)
    lang_parser.add_argument(
        '--lang',
        help='Override target language (instead of inferring from filename)'
    )

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

    # Scan subcommand — single file only (Stage 3 behavior)
    # Does NOT use po_input_parser because it doesn't accept --include
    scan_parser = subparsers.add_parser(
        "scan",
        parents=[sort_parser, glossary_parser, context_parser],
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

    # Import subcommand — uses all relevant parent parsers
    import_parser = subparsers.add_parser(
        "import",
        parents=[master_parser, po_input_parser, sort_parser, glossary_parser, context_parser, lang_parser],
        help="Import PO file translations into master CSV"
    )

    # Export subcommand — uses parent parsers + own flags
    export_parser = subparsers.add_parser(
        "export",
        parents=[master_parser, po_input_parser, sort_parser, lang_parser],
        help="Export master CSV translations back to PO files"
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
        "-v", "--verbose",
        action="store_true",
        help="Show per-entry detail"
    )

    # Lint subcommand — uses glossary and context parsers, but has custom file handling
    # Cannot use po_input_parser because lint has optional positional 'file' instead of 'po_files'
    lint_parser = subparsers.add_parser(
        "lint",
        parents=[glossary_parser, context_parser],
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

    # Translate subcommand — uses master, lang, glossary parsers
    translate_parser = subparsers.add_parser(
        "translate",
        parents=[master_parser, lang_parser, glossary_parser],
        help="Machine-translate entries in master CSV via DeepL API"
    )

    translate_parser.add_argument(
        "--auth-key",
        help="DeepL API authentication key (or set DEEPL_AUTH_KEY env var)"
    )

    translate_parser.add_argument(
        "--status",
        action="append",
        default=None,
        help="Which statuses to translate (repeatable, default: empty)"
    )

    translate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Estimate cost without calling DeepL API"
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
    elif args.command == "translate":
        return cmd_translate(args)
    elif args.command is None:
        parser.print_help()
        return 1
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
