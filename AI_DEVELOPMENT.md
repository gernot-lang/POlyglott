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

## Why Document This?

Most projects show the end result but not how they got there. The prompts directory preserves the methodology — useful for anyone exploring AI-assisted development workflows.
