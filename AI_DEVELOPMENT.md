# Building POlyglott with Claude Code

POlyglott was built using [Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview), Anthropic's command-line tool for AI-assisted development. This document briefly explains the approach.

## How It Works

Each development stage has a specification in the `prompts/` directory. These specs were written by a human and fed to Claude Code as prompts. Claude Code then implemented the feature, wrote tests, and updated documentation — with human review at each step.

The specifications evolved as the project progressed. Lessons from earlier stages informed later ones. What you see in `prompts/` reflects real experience, not first drafts.

## The Stage Prompts

| Prompt      | Delivers                                   | Version |
|-------------|--------------------------------------------|---------|
| `stage1.md` | PO scanning and CSV export                 | v0.1.0  |
| `stage2.md` | Lint subcommand with glossary support      | v0.2.0  |
| `stage3.md` | Context inference from source references   | v0.3.0  |
| `stage4.md` | Translation master CSV with merge workflow | v0.4.0  |
| `stage5.md` | DeepL integration for machine translation  | v0.5.0  |

Each prompt specifies scope boundaries, implementation details, test expectations, and documentation requirements. They are self-contained — Claude Code can execute a stage from its prompt alone, using `CLAUDE.md` for project-level conventions.

## Git History

The git history reflects actual execution against these specs. Feature branches show Claude Code's work; merge commits on `develop` and `main` mark stage completions.

### Feature Development vs Bugfixes

**Feature branches** (stages):
- Branch from `develop`
- Implement feature with tests
- Bump minor version (0.1.0 → 0.2.0)
- Merge develop → main → tag

**Bugfix branches** (post-release):
- Branch from `main` (fixes production code)
- **TDD required**: Write failing test first
- Fix the issue
- Update CHANGELOG
- Merge to both develop and main
- Bump patch version (0.3.1 → 0.3.2)
- Tag on main

Example: v0.3.1 added error handling, v0.3.2 fixed the actual glossary validation bug (with TDD).

## Development Practices

### Test-Driven Development (TDD)

POlyglott follows TDD, especially for bugfixes:

1. **Write failing test** that reproduces the bug
2. **Verify it fails** with the exact error users reported
3. **Fix the code** to make the test pass
4. **Verify all tests pass** including the new one

This approach:
- Ensures bugs are actually fixed (not just symptoms)
- Prevents regressions through test coverage
- Documents the bug's reproduction steps
- Provides confidence in the fix

Example from v0.3.2:
- User reported: `'list' object has no attribute 'items'`
- Added test with list-format glossary → FAILED ✓
- Fixed validation in `linter.py` → PASSED ✓
- All 138 tests passing → Shipped ✓

### CHANGELOG Discipline

Every release (feature or bugfix) updates `CHANGELOG.md` **before** tagging:
- User-facing descriptions, not implementation details
- Grouped by Added, Changed, Fixed, Removed
- Clear, concise explanations of what changed

This makes the git history self-documenting for users.

## Why Document This?

Most projects show the end result but not how they got there. The prompts directory preserves the methodology — useful for anyone exploring AI-assisted development workflows.

This includes the mistakes (like v0.3.1 fixing the wrong thing) and the corrections (v0.3.2 with TDD). Real development isn't linear; this history shows the actual process.
