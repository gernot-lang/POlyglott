# POlyglott

A tool for parsing gettext PO files and exporting them to CSV for translation workflow management.

## Features

- **PO File Parsing**: Extract all metadata from gettext PO files using polib
- **CSV Export**: Convert PO entries to CSV format with pandas
- **Quality Linting**: Check translations for common issues (untranslated, fuzzy, format mismatches)
- **Glossary Support**: Enforce translation consistency with YAML glossary files
- **Multi-file Support**: Process multiple PO files with glob patterns
- **Unicode Support**: Full support for international characters, emoji, and multi-byte scripts
- **Flexible Sorting**: Sort output by any field (msgid, msgstr, fuzzy status, etc.)
- **Statistics**: View translation progress (total, untranslated, fuzzy, plurals)
- **Command-line Interface**: Easy-to-use CLI with intuitive options

## Installation

### From Source

```bash
git clone <repository-url>
cd polyglott
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Requirements

- Python 3.10 or higher
- polib >= 1.2.0
- pandas >= 2.0.0
- pyyaml >= 6.0

## Usage

### Scan Command

Scan a single PO file and output to stdout:

```bash
polyglott scan messages.po
```

Save output to a CSV file:

```bash
polyglott scan messages.po -o output.csv
```

#### Multi-file Processing

Process multiple PO files using glob patterns:

```bash
polyglott scan --include "locales/**/*.po" -o translations.csv
```

Exclude specific files:

```bash
polyglott scan --include "**/*.po" --exclude "tests/**/*.po" -o output.csv
```

#### Sorting

Sort output by field:

```bash
polyglott scan messages.po --sort-by msgid -o sorted.csv
```

Available sort fields: `msgid`, `msgstr`, `source_file`, `fuzzy`

### Lint Command

Check translation quality with built-in validators:

```bash
polyglott lint messages.po
```

#### Text Output

Human-readable text format for terminal:

```bash
polyglott lint messages.po --format text
```

#### Glossary Checking

Enforce term consistency with a glossary file:

```bash
polyglott lint messages.po --glossary glossary.yaml
```

**Glossary Format (YAML):**

```yaml
language: de
terms:
  file: Datei
  folder: Ordner
  pipeline: Pipeline
```

#### Built-in Checks

- **untranslated** (error): Entry has no translation
- **fuzzy** (warning): Entry is marked as fuzzy
- **format_mismatch** (error): Format placeholders don't match (e.g., `%(name)s`, `{count}`)
- **term_mismatch** (warning): Translation doesn't use glossary term
- **obsolete** (info): Entry is marked as obsolete

#### Filtering

Filter by severity level:

```bash
polyglott lint messages.po --severity error  # Only errors
```

Include/exclude specific checks:

```bash
polyglott lint messages.po --check untranslated --check fuzzy
polyglott lint messages.po --no-check obsolete
```

#### Exit Codes

- `0`: No issues found
- `1`: Errors found
- `2`: Warnings found (no errors)

Perfect for CI/CD pipelines:

```bash
polyglott lint locales/de.po || exit 1
```

### Examples

**Scan single file with sorting:**

```bash
polyglott scan de.po --sort-by msgid -o german.csv
```

**Scan multiple languages:**

```bash
polyglott scan --include "locales/*/LC_MESSAGES/*.po" -o all_translations.csv
```

**Lint with glossary in CI:**

```bash
polyglott lint locales/de.po --glossary glossaries/de.yaml --severity warning
```

**Lint all files with text output:**

```bash
polyglott lint --include "**/*.po" --exclude "vendor/*.po" --format text
```

## Output Format

### Scan CSV Columns

- `msgid`: Original message string
- `msgstr`: Translated string
- `msgctxt`: Message context (optional)
- `extracted_comments`: Comments extracted from source code
- `translator_comments`: Translator-added comments
- `references`: Source code locations (file:line)
- `fuzzy`: Fuzzy translation flag (True/False)
- `obsolete`: Obsolete entry flag (True/False)
- `is_plural`: Plural form flag (True/False)
- `plural_index`: Plural form index (0, 1, 2, ...)

Multi-file mode adds `source_file` as the first column.

### Lint CSV Columns

Lint mode adds three additional columns:

- `severity`: error, warning, or info
- `check`: Name of the check that failed
- `message`: Description of the issue

### Lint Text Format

```
format_issues.po:
-----------------
  ERROR   line 15    format_mismatch      Format placeholder mismatch (missing: %(value)s)
  ERROR   line 20    format_mismatch      Format placeholder mismatch (extra: %(extra)s)

------------------------------------------------------------
2 errors — 2 issues in 1 file
```

## Statistics

POlyglott displays statistics to stderr (keeping stdout clean for CSV output):

```
Statistics:
  Total entries: 245
  Untranslated: 42
  Fuzzy: 8
  Plurals: 15
  Files processed: 3
```

## Use Cases

- **Translation Management**: Export PO files to CSV for review in spreadsheet tools
- **Quality Assurance**: Lint translations for common issues before deployment
- **CI/CD Integration**: Enforce translation quality in automated pipelines
- **Glossary Enforcement**: Ensure consistent terminology across translations
- **Progress Tracking**: Monitor translation completion across multiple languages
- **Data Analysis**: Analyze translation patterns with pandas or Excel

## Development

### Running Tests

```bash
pytest              # Run all tests
pytest -v           # Verbose output
pytest tests/test_parser.py  # Specific module
```

### Project Structure

```
src/polyglott/
├── __init__.py      # Package init with __version__
├── __main__.py      # Support for python -m polyglott
├── cli.py           # CLI entry point (argparse)
├── parser.py        # PO file parsing (polib)
├── exporter.py      # CSV export (pandas)
├── linter.py        # Quality checks and glossary
└── formatter.py     # Text output formatting
```

## Roadmap

POlyglott is under active development:

- **Stage 1 (v0.1.0)**: ✅ PO scanning and CSV export
- **Stage 2 (v0.2.0)**: ✅ Lint subcommand with glossary support
- **Stage 3 (v0.3.0)**: Context inference from source code references
- **Stage 4 (v0.4.0)**: Translation master CSV for multi-language management
- **Stage 5 (v0.5.0)**: DeepL integration for machine translation

See `prompts/` directory for detailed stage specifications.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see [LICENSE.md](LICENSE.md) for details.

## Acknowledgments

Built with:

- [polib](https://pypi.org/project/polib/) - PO file parsing
- [pandas](https://pandas.pydata.org/) - Data manipulation and CSV export
- [pyyaml](https://pyyaml.org/) - Glossary file parsing
- [pytest](https://pytest.org/) - Testing framework
