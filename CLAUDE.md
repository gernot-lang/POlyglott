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

### Version Bumping

Use the venv's bump-my-version (not system Python):

```bash
.venv/bin/bump-my-version bump minor  # 0.1.0 → 0.2.0
.venv/bin/bump-my-version bump patch  # 0.1.0 → 0.1.1
```

**Important:** Configuration uses `[tool.bumpversion]` (not `[tool.bump-my-version]`) in pyproject.toml.

### CLI

```bash
polyglott --version
polyglott scan <po-file> -o output.csv
```

> **Note:** CLI commands grow with each stage. See stage prompts in `prompts/` for details.

## Architecture

### Package Structure

```
src/polyglott/
├── __init__.py      # Package init with __version__
├── __main__.py      # Support for python -m polyglott
├── cli.py           # CLI entry point (argparse)
├── parser.py        # PO file parsing (polib)
└── exporter.py      # CSV export (pandas)
```

> **Note:** Modules are added per stage. Each stage prompt specifies new modules.

### Core Dependencies

- **polib**: PO file parsing
- **pandas**: DataFrame manipulation and CSV export
- **pytest**: Testing
- **bump-my-version**: Version management

## Git Workflow

POlyglott uses a simplified Git Flow with no squash merges.

### Branch Structure

- **main**: Production releases, tagged with annotated version tags
- **develop**: Integration branch for completed features
- **feature/***: One feature branch per stage

### Feature Development (per stage)

```bash
# 1. Create feature branch from develop
git checkout develop
git checkout -b feature/feature-name

# 2. Develop with regular commits (good messages, no version bumps)
git add .
git commit -m "feat(parser): add PO file parsing with metadata extraction"

# 3. When feature is complete, merge to develop (no squash, no fast-forward)
git checkout develop
git merge --no-ff feature/feature-name

# 4. Bump version on develop
bump-my-version bump minor

# 5. Update CHANGELOG.md (move Unreleased items to version section with date)
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG for vX.Y.0"

# 6. Merge develop to main
git checkout main
git merge --no-ff develop

# 7. Create annotated tag on main
git tag -a vX.Y.0 -m "Short description of what this release delivers"

# 8. Push everything
git push origin main develop --tags

# 9. Delete feature branch
git branch -d feature/feature-name
```

### Bugfix Workflow (after release)

Manual testing happens after tagging a release on `main`. If bugs or deficiencies are found:

**CRITICAL: Follow Test-Driven Development (TDD) for all bugfixes:**
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

# 10. Tag with descriptive message
git tag -a v0.X.Y -m "Fix description (concise)"

# 11. Update version test (if exists)
# Edit tests/test_cli.py version check to match new version
git add tests/test_cli.py
git commit -m "test: update version check to 0.X.Y"

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

### Key Rules

- **No squash merges** — preserve commit history, use `--no-ff` everywhere
- **One version bump per stage** — no intermediate version bumps during development
- **Annotated tags only** — `git tag -a` with descriptive messages
- **Version bump happens on develop** — before merging to main (for features)
- **Bugfix version bump on main** — patch bump after fix merges to both branches

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
| 5     | v0.5.0  | DeepL integration                        | `feature/deepl`             |

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

**Do NOT create additional .md files.** All user documentation goes into `README.md`.

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
