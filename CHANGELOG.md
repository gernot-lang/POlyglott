# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.0] - 2026-02-12

### Added

- `candidate` column in master CSV for non-destructive machine translation suggestions
- Column sovereignty: user-added columns are now preserved across all operations (import, translate, export)
- Translation routing: `translate` writes to `msgstr` when empty, `candidate` when msgstr already exists

### Changed

- Master CSV now supports arbitrary user-added columns beyond POlyglott's reserved columns
- `translate` subcommand summary shows routing breakdown (msgstr vs candidate writes)
- Dry-run output shows where translations will be written based on current msgstr state
- Master CSV column order: POlyglott columns first, user columns after (maintains stable ordering)

## [0.6.2] - 2026-02-12

### Fixed

- Translation now properly handles ampersands, angle brackets, and other XML-unsafe characters in message text. Previously, entries containing `&`, `<`, or `>` outside format placeholders would fail with "Tag handling parsing failed" error from DeepL API. The fix escapes these characters before sending to DeepL and restores them after translation.

## [0.6.1] - 2026-02-12

### Fixed

- DeepL translation now accepts source language correctly - fixed "Bad request. Reason: Value for 'source_lang' not supported" error that occurred when translating from English or other languages. DeepL requires base language codes (EN, DE, FR) for source languages, not regional variants (EN-US, EN-GB).

### Changed

- `translate` subcommand now uses `--target-lang` and `--source-lang` flags for clarity (instead of `--lang`). Source language defaults to English but can now be explicitly configured.

### Added

- Context parameter is now passed to DeepL API when available, enabling context-aware translations for better accuracy.

## [0.6.0] - 2026-02-12

### Added

- `translate` subcommand for machine translation via DeepL API
- Strategy C placeholder protection using XML tags with `ignore_tags="x"` for correct word order
- `--auth-key` flag for DeepL API authentication (or use `DEEPL_AUTH_KEY` environment variable)
- `--status` flag to specify which entry statuses to translate (default: empty)
- `--dry-run` flag to estimate translation cost without API calls
- Automatic status transition from empty/rejected → machine after translation
- Passthrough detection for non-translatable strings (OK, N/A, placeholder-only, punctuation)
- HTML entity protection to prevent mistranslation of &amp;, &lt;, &gt;, etc.
- Multiline translation with line-by-line processing to preserve formatting
- Ephemeral glossary support for protecting key terms during translation
- Spacing normalization post-processor for consistent placeholder formatting
- Graceful error handling with progress saving on quota exceeded or network failures
- Optional `deepl` dependency group installable via `pip install "polyglott[deepl]"`
- Character count estimation for cost planning in dry-run mode

## [0.5.2] - 2026-02-12

### Fixed

- Export counter now properly distinguishes write/overwrite/skip states - running export twice on unchanged files correctly reports 0 writes on the second run
- Fixed hardcoded version assertion in CLI tests to use dynamic import

## [0.5.1] - 2026-02-12

### Added

- `--include` flag for `import` subcommand to specify glob patterns for PO file discovery
- `--include` flag for `export` subcommand to specify glob patterns for PO file discovery
- `--sort-by` flag for `import` subcommand to control master CSV sort order
- `--sort-by` flag for `export` subcommand to control output sort order
- Shared `resolve_po_files()` helper for unified PO file collection across subcommands
- Support for combining positional files with `--include` patterns (union of both sources)
- Warning message when `--include` pattern matches no files
- Error message when all files are excluded by `--exclude` patterns

### Changed

- **BREAKING**: `import` and `export` now require `--master` flag instead of positional master CSV argument
- **BREAKING**: Master CSV is now specified explicitly with `--master` flag for clarity
- CLI refactored to use argparse parent parsers for shared flags (eliminates future omissions)
- PO file resolution now handles both positional arguments and `--include` patterns consistently
- Error messages improved with clearer guidance when no PO files are specified

### Migration Guide

- Old: `polyglott import master-de.csv locale/**/*.po`
- New: `polyglott import --master master-de.csv locale/**/*.po`

- Old: `polyglott export master-de.csv locale/**/*.po`
- New: `polyglott export --master master-de.csv locale/**/*.po`

Positional PO files and `--include` patterns can be combined:

```bash
polyglott import --master master-de.csv \
  locale/de/LC_MESSAGES/django.po \
  --include "apps/**/de/LC_MESSAGES/*.po" \
  --exclude "apps/legacy/**"
```

## [0.5.0] - 2026-02-12

### Added

- `import` subcommand for importing PO file translations into master CSV
- `export` subcommand for writing master CSV translations back to PO files
- Flexible master CSV naming with language inference from `-<lang>.csv` suffix (e.g., `master-de.csv`, `help-pages-de.csv`)
- `--lang` flag for explicit language override on import and export
- `--status` flag for export to filter which translation statuses to write (default: accepted)
- `--dry-run` flag for export to preview changes without modifying PO files
- `--verbose` / `-v` flag for export to show per-entry detail
- Automatic fuzzy flag management on export (clear for accepted, set for machine, preserve for review)
- Bidirectional PO file sync workflow (import → review → export)
- Support for multi-part language codes (en-us, pt-br, zh-hans)

### Changed

- Restored `scan` subcommand to Stage 3 behavior (single file, per-file CSV export only)
- Master CSV operations now use dedicated `import` subcommand instead of `scan --master`
- All console output now uses full file paths (not basenames) for clarity

### Removed

- `--master` flag from `scan` subcommand (use `import` instead)
- `--include` and `--exclude` flags from `scan` (use `import` for multi-file operations)
- Strict `polyglott-accepted-<lang>.csv` filename requirement (now accepts any `*-<lang>.csv` pattern)

### Migration Guide

- Old: `polyglott scan --master polyglott-accepted-de.csv locale/de/LC_MESSAGES/*.po`
- New: `polyglott import polyglott-accepted-de.csv locale/de/LC_MESSAGES/*.po`

## [0.4.0] - 2026-02-11

### Added

- Translation master CSV for project-wide translation management
- `--master` flag for scan command to create/update master CSV instead of regular export
- Deduplication by msgid across multiple PO files (single master row per msgid)
- Status tracking with lifecycle: empty → review → accepted/rejected → stale/conflict
- Merge workflow that preserves human decisions (accepted/rejected status) across rescans
- Conflict detection when PO files diverge from accepted translations
- Automatic quality scoring for exact glossary matches (score: 10)
- Context refresh on every rescan (reflects current codebase state)
- Majority voting for msgstr conflict resolution when deduplicating
- Reference aggregation from all source files for context inference
- Master CSV validation: filename must match `polyglott-accepted-<lang>.csv` pattern
- Master CSV with UTF-8 BOM encoding, all fields quoted (QUOTE_ALL), sorted by msgid
- 12+ status transition rules for merge workflow
- Comprehensive test suite for master CSV functionality (46 additional tests)

## [0.3.3] - 2026-02-11

### Fixed

- Glossary term matching is now fully case-insensitive for both source and translation
- Glossary keys are normalized to lowercase on load (e.g., `File:` and `file:` treated identically)
- Translation matching now uses case-insensitive comparison (e.g., `Pipeline` matches `pipeline`)
- Fixes false positives where capitalization differences caused term mismatch warnings

## [0.3.2] - 2026-02-11

### Fixed

- Glossary validation now properly checks that `terms` is a dictionary, not a list
- Clear error message when glossary uses incorrect list format (e.g., `- source: file`)
- Prevents cryptic "'list' object has no attribute 'items'" error during lint

## [0.3.1] - 2026-02-11

### Added

- Better error handling in CSV export with descriptive messages for DataFrame creation issues
- Row-level error tracking to identify problematic entries during export

## [0.3.0] - 2026-02-11

### Added

- Context inference from PO file source references (`#:` comments)
- `--context-rules` flag for scan and lint to load custom YAML context mapping rules
- `--preset django` flag for built-in Django path convention mapping
- `context` and `context_sources` columns in CSV output when context inference is active
- Ambiguity handling for entries with multiple conflicting context sources
- Django preset with 11 common patterns (forms, models, views, templates, admin, etc.)
- Substring-based pattern matching with first-match-wins rule order
- Majority voting and tie detection for multi-reference entries
- Comprehensive test suite for context inference (35 additional tests)
- Full backward compatibility — context features are opt-in via flags

## [0.2.0] - 2026-02-11

### Added

- `lint` subcommand for translation quality checks with configurable severity levels
- Built-in quality checks: untranslated, fuzzy, obsolete, format_mismatch
- Format placeholder validation for both percent-style (%(name)s) and brace-style ({name}) formats
- YAML glossary support for enforcing translation consistency
- Word-boundary term matching to prevent false positives
- Text output format for human-readable lint results
- CSV lint output with severity, check name, and message columns
- Severity filtering (--severity error/warning/info)
- Check filtering (--check/--no-check for including/excluding specific checks)
- Exit codes for CI/CD integration (0=clean, 1=errors, 2=warnings)
- Comprehensive test suite for linter, formatter, and glossary (68 additional tests)

## [0.1.0] - 2026-02-11

### Added

- PO file parsing with full metadata extraction (msgid, msgstr, msgctxt, comments, references, flags)
- CSV export with pandas for single and multiple PO files
- CLI with `scan` subcommand for basic PO file processing
- Multi-file scanning with glob pattern support (--include/--exclude)
- Field-based sorting (--sort-by msgid/msgstr/fuzzy/source_file)
- Unicode support for international characters, emoji, and multi-byte scripts
- Statistics display (total, untranslated, fuzzy, plurals)
- Handling of plural forms, fuzzy translations, and obsolete entries
- Comprehensive test suite (34 tests covering parser, exporter, and CLI)

[Unreleased]: #

[0.4.0]: #

[0.3.3]: #

[0.3.2]: #

[0.3.1]: #

[0.3.0]: #

[0.2.0]: #

[0.1.0]: #
