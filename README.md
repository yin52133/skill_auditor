# skill-auditor

`skill-auditor` is a planned audit and maintenance tool for Codex and Claude Code skills.

Current repository state:

- canonical design lives in [`SPEC.md`](./SPEC.md)
- implementation tracking lives in [`checklist.json`](./checklist.json)
- design revision history lives in [`update_history`](./update_history)
- upstream reference analysis lives in [`ref/skill-creator-analysis.md`](./ref/skill-creator-analysis.md)

## Goal

This project is intended to:

- audit skill structure and required metadata
- detect missing Codex- or Claude-specific requirements
- cluster duplicated or overlapping skills
- flag likely trigger-quality and maintenance problems
- maintain per-skill audit state and source provenance
- support watch mode and git-hook based audit triggers
- recommend a smaller active auto-trigger set

The design explicitly separates:

- deterministic findings: hard schema and contract violations
- heuristic findings: overlap, smell, and likely trigger issues

## Current Status

This repository is in spec-first stage.

Included now:

- first complete design spec
- reference analysis against the OpenAI Codex and Anthropic skill-creator examples
- initial execution checklist
- initial update history entry

Not included yet:

- Python implementation
- CLI commands
- watch mode
- git hooks
- clustering engine

## Repository Files

| Path | Purpose |
|------|---------|
| `SPEC.md` | current complete design |
| `checklist.json` | implementation tracker for this repo |
| `update_history` | append-only design revision log |
| `ref/` | local reference analysis and ignored upstream clones |
| `.gitignore` | local repo ignore rules, including cloned references |

## Reference Sources

The design is based on these upstream references, cloned locally under `ref/` and ignored from git:

- OpenAI Codex sample skill-creator
- Anthropic skill-creator

The extracted cross-reference notes are committed in `ref/skill-creator-analysis.md`.

## Privacy and Security Notes

This repository should not commit:

- API keys, tokens, credentials, or private keys
- user-specific secrets or auth material
- local cloned upstream repos under `ref/openai-codex/` and `ref/anthropics-skills/`

Committed content may still mention generic target paths such as `~/.codex/skills` or `~/.claude/skills` because they are part of the product design, not machine-specific secrets.
