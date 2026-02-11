# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[0.3.2]: #

[0.3.1]: #

[0.3.0]: #

[0.2.0]: #

[0.1.0]: #
