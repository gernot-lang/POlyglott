# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

POlyglott is a **generic OSS tool** for parsing gettext PO files and exporting them to CSV for translation workflow management. This is NOT company-specific code — avoid any references to GRAPE, Softwerk, or other company implementations.

## Development Commands

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Testing

```bash
pytest              # Run all tests
pytest -v           # Verbose output
pytest tests/test_parser.py  # Specific file
```

## Known Issues

### Export write counter (po_writer.py)

Export reports all matching entries as "writes" even when PO msgstr already matches master CSV.
Second consecutive export should report 0 writes but reports the same count as the first run.

**Required fix:** Three-state counting:

- **write**: PO msgstr was empty, filled from master
- **overwrite**: PO msgstr had a different value, replaced by master
- **skip**: PO msgstr already matches master

Console output should reflect all three states. Idempotent export must report 0 writes on second run.

### Version Bumping

Use the venv's bump-my-version (not system Python):

```bash
.venv/bin/bump-my-version bump minor  # 0.1.0 → 0.2.0
.venv/bin/bump-my-version bump patch  # 0.1.0 → 0.1.1
```

**Important:** Configuration uses `[tool.bumpversion]` (not `[tool.bump-my-version]`) in pyproject.toml. `tag = false` in pyproject.toml — tagging is handled manually in the workflow, never by bump-my-version.

### CLI

```bash
polyglott --version
polyglott scan <po-file> -o output.csv
polyglott lint --include "**/*.po" --glossary glossary.yaml
polyglott import --master master-de.csv --include "locale/de/**/*.po"
polyglott export --master master-de.csv --include "locale/de/**/*.po" --dry-run
```

> **Note:** Run `polyglott <subcommand> --help` for full flag details. CLI flags grow with each stage — see stage prompts in `prompts/` for specifications.

## Architecture

### Package Structure

```
src/polyglott/
├── __init__.py      # Package init with __version__
├── __main__.py      # Support for python -m polyglott
├── cli.py           # CLI entry point (argparse)
├── parser.py        # PO file parsing (polib)
├── exporter.py      # CSV export (pandas)
├── linter.py        # PO quality checks
├── formatter.py     # Output formatting
├── context.py       # Context inference from source references
├── master.py        # Master CSV creation, merge, deduplication
└── po_writer.py     # Export master CSV translations back to PO files
```

> **Note:** Modules are added per stage. Each stage prompt specifies new modules.

### Core Dependencies

- **polib**: PO file parsing
- **pandas**: DataFrame manipulation and CSV export
- **pyyaml**: Glossary and context rules
- **pytest**: Testing
- **bump-my-version**: Version management

### Version Testing

Do NOT hardcode version strings in tests. Import from the package:

```python
from polyglott import __version__


def test_version():
    assert __version__  # just verify it exists and is non-empty
```

## Git Workflow

POlyglott uses a simplified Git Flow with no squash merges.

**Claude Code executes the full git workflow** — branching, committing, merging, bumping, and tagging. Always follow the exact sequences below. In particular:

- **Create `develop` from `main`** if it doesn't exist
- **Create `feature/*` from `develop`**, never from `main`
- **Create `fix/*` from `main`**, never from `develop`
- **Never commit directly to `main` or `develop`** — always work on a feature or fix branch
- **Never delete `main` or `develop`** — only delete feature/* and fix/* branches after merging

### Branch Structure

- **main**: Production releases, tagged with annotated version tags
- **develop**: Integration branch for completed features
- **feature/***: One feature branch per stage
- **fix/***: Bugfix branches after release

### Feature Development (per stage)

```bash
# 1. Create feature branch from develop
git checkout develop
git checkout -b feature/feature-name

# 2. Develop with regular commits (good messages, no version bumps)
git add .
git commit -m "feat(parser): add PO file parsing with metadata extraction"

# 3. When feature is complete, run verification gate (see Pre-Merge Verification Gate)
polyglott scan --help
polyglott import --help
polyglott export --help
polyglott lint --help
# Verify all --help output matches stage spec. Fix discrepancies before merging.

# 4. Merge to develop (no squash, no fast-forward)
git checkout develop
git merge --no-ff feature/feature-name

# 5. Bump version on develop
.venv/bin/bump-my-version bump minor

# 6. Update CHANGELOG.md (move Unreleased items to version section with date)
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG for vX.Y.0"

# 7. Merge develop to main
git checkout main
git merge --no-ff develop

# 8. VERIFY you're on main before tagging
git branch --show-current  # MUST show "main"

# 9. Create annotated tag on main
git tag -a vX.Y.0 -m "Short description of what this release delivers"

# VERIFY THE TAG:
git show vX.Y.0 --no-patch --format="%d %s"

# 10. Push everything
git push origin main develop --tags

# 11. Delete feature branch
git branch -d feature/feature-name
```

### Bugfix Workflow (after release)

Manual testing happens after tagging a release on `main`. If bugs or deficiencies are found:

**⚠️ CRITICAL REQUIREMENTS:**

1. **Always verify current branch before tagging**
    - Tags MUST be on main, on the version bump commit
    - Use `git branch --show-current` before EVERY tag operation
    - NEVER tag while on a feature/fix branch

2. **Follow Test-Driven Development (TDD) for all bugfixes:**
    1. Write a failing test that reproduces the bug
    2. Verify the test fails with the exact error
    3. Fix the code
    4. Verify the test passes
    5. Ensure all other tests still pass

```bash
# 1. Branch from main (where the tag is)
git checkout main
git checkout -b fix/description

# 2. Write failing test first (TDD)
# Add test to appropriate test_*.py file that reproduces the bug
pytest tests/test_module.py::test_new_bug -v  # Should FAIL

# 3. Fix the issue
# Implement the fix in source code

# 4. Verify test passes
pytest tests/test_module.py::test_new_bug -v  # Should PASS
pytest  # All tests must pass

# 5. Commit fix and test together
git add .
git commit -m "fix(scope): description

- Add test to reproduce bug
- Fix actual issue
- Clear explanation of root cause"

# 6. Update CHANGELOG.md (MANDATORY)
# Add entry under new [0.X.Y] section with:
# - Clear description of what was fixed
# - User-facing impact, not implementation details
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG for v0.X.Y"

# 7. Merge to develop first (so develop stays current)
git checkout develop
git merge --no-ff fix/description

# 8. Merge to main
git checkout main
git merge --no-ff fix/description

# 9. Bump patch version on main
.venv/bin/bump-my-version bump patch

# 10. CRITICAL: Verify you're on main and tag the version bump commit
git branch --show-current  # MUST show "main"
git log --oneline -1       # MUST show "chore: bump version X.Y.Z → X.Y.Z+1"

# 11. Tag with descriptive message (ONLY after verification above)
git tag -a v0.X.Y -m "Fix description (concise)"

# VERIFY THE TAG IS CORRECT:
git show v0.X.Y --no-patch --format="%d %s"  # Should show the version bump commit

# 12. Push everything
git push origin main develop --tags

# 13. Clean up
git branch -d fix/description
```

**Key differences from feature branches:**

- Branch from **main** (not develop) — fixes production code
- Merge to **both** main and develop (not just develop)
- Bump **patch** version (0.3.1 → 0.3.2), not minor
- Version bump happens on **main** (not develop)
- **TDD is mandatory** — test must reproduce bug before fixing
- **CHANGELOG must be updated** — document the fix for users

### Pre-Merge Verification Gate

**MANDATORY before version bump, merge to main, and tagging.** This catches spec-vs-reality drift in both directions — flags the spec promised but code didn't implement, and flags code added that the spec didn't describe.

```bash
# 1. Capture actual CLI state
polyglott scan --help
polyglott import --help
polyglott export --help
polyglott lint --help

# 2. Verify against stage spec
# For each subcommand, confirm:
# - All spec'd flags are present
# - No unexpected flags appeared
# - Flag choices/defaults match spec
# - Positional arguments match spec
# - Required vs optional matches spec

# 3. Run full test suite
pytest

# 4. Verify no regressions in existing subcommands
# - Do subcommands that should be unchanged still match their pre-stage --help output?
```

**If any discrepancy is found:** fix code or update spec before proceeding. Never merge with known spec-vs-reality drift.

**For stage spec authors:** always capture `--help` output from the actual CLI as the baseline before writing the spec. Never derive flag inventories from earlier stage documents alone.

### Key Rules

- **No squash merges** — preserve commit history, use `--no-ff` everywhere
- **One version bump per stage** — no intermediate version bumps during development
- **Annotated tags only** — `git tag -a` with descriptive messages
- **Version bump happens on develop** — before merging to main (for features)
- **Bugfix version bump on main** — patch bump after fix merges to both branches
- **Never delete `main` or `develop`** — only delete feature/* and fix/* branches
- **Never commit directly to `main` or `develop`** — always use a branch
- **Always use `.venv/bin/bump-my-version`** — never the system-installed version
- **Always run verification gate** — before merging any feature or fix branch

### Commit Messages

Follow Conventional Commits:

```
feat(scope): description     # New feature
fix(scope): description      # Bug fix
test(scope): description     # Adding tests
docs: description            # Documentation
refactor(scope): description # Restructuring
chore: description           # Maintenance
```

## Staged Development Plan

| Stage | Version | Feature                                  | Branch                      |
|-------|---------|------------------------------------------|-----------------------------|
| 1     | v0.1.0  | PO scanning and CSV export               | `feature/scan`              |
| 2     | v0.2.0  | Lint subcommand with glossary            | `feature/lint`              |
| 3     | v0.3.0  | Context inference from source references | `feature/context-inference` |
| 4     | v0.4.0  | Translation master CSV                   | `feature/master-csv`        |
| 5     | v0.5.0  | Import/export subcommands, scan restore  | `feature/import-export`     |
| 5.1   | v0.5.1  | CLI harmonization, parent parsers        | `feature/cli-harmonization` |
| 6     | v0.6.0  | DeepL integration                        | `feature/deepl`             |

See `prompts/stageX.md` for detailed specifications.

## CHANGELOG Requirements

Follow [Keep a Changelog](https://keepachangelog.com/) strictly:

- **User-focused entries**: what users get, not implementation details
- **Good**: "Multi-file scanning with glob patterns"
- **Bad**: "Refactored MultiPOParser class to use generator pattern"
- Group by: Added, Changed, Fixed, Removed
- Always maintain `[Unreleased]` section at top

## Project Files

| File                | Purpose                                          |
|---------------------|--------------------------------------------------|
| `README.md`         | Public-facing: features, install, usage, roadmap |
| `LICENSE.md`        | MIT License                                      |
| `CHANGELOG.md`      | Release notes, Keep a Changelog format           |
| `CLAUDE.md`         | This file — Claude Code project instructions     |
| `AI_DEVELOPMENT.md` | How this project was built with Claude Code      |
| `prompts/stageX.md` | Stage specifications used as Claude Code prompts |
| `reviews/`          | Code review reports and template                 |

**Do NOT create additional .md files** except in `prompts/` and `reviews/`.
All user documentation goes into `README.md`.

## Important Constraints

### Generic OSS Tool

- NO references to GRAPE, Softwerk, or company-specific implementations
- `.claudeignore` blocks contamination from adjacent project directories
- This is a standalone tool for the translation community

### Code Style

- PEP 8
- Docstrings on public APIs
- Functions focused and single-purpose
- Test edge cases (Unicode, malformed PO files, plurals)

### Testing Discipline

**Test-Driven Development (TDD):**

POlyglott follows TDD principles, especially for bugfixes:

1. **For new features**: Write tests alongside implementation (test as you go)
2. **For bugfixes**: ALWAYS write failing test first, then fix
3. **Verify tests fail**: Before fixing, confirm test reproduces the actual error
4. **Verify tests pass**: After fixing, confirm test passes and all others still pass

**Testing Requirements:**

- All tests must pass before considering a stage complete
- Each stage adds tests for its new functionality
- Existing tests must continue to pass — no regressions
- Bugfix tests must reproduce the exact error users reported
- Test edge cases (Unicode, malformed PO files, plurals, empty data)
- Use descriptive test names that explain what is being tested
- Do NOT hardcode version strings in tests — import `__version__` from package
