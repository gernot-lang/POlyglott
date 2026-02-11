# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[0.1.0]: #
