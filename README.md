# skill-auditor

`skill-auditor` is a planned audit and maintenance tool for Codex and Claude Code skills.

Current repository state:

- canonical design lives in [`docs/spec/spec.md`](./docs/spec/spec.md)
- implementation tracking lives in [`docs/spec/checklist.json`](./docs/spec/checklist.json)
- design revision history lives in [`docs/spec/update_history`](./docs/spec/update_history)
- upstream reference analysis lives in [`docs/spec/references.md`](./docs/spec/references.md)
- Python implementation lives in [`src/skill_auditor/`](./src/skill_auditor/)
- test coverage lives in [`tests/`](./tests/)

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

This repository is in implementation stage.

Included now:

- first complete design spec
- reference analysis against the OpenAI Codex and Anthropic skill-creator examples
- initial execution checklist
- initial update history entry
- Python package and CLI entry points
- deterministic audit pipeline for Codex and Claude-targeted skill folders
- runtime state writes for audit runs, ledgers, index, clusters, and active set
- watch-session primitives plus hook installer and hook-run support
- pytest coverage for discovery, security, state, overlap, watch, and hook flows

Not included yet:

- remote provenance sync
- explicit prune flow for stale ledgers
- richer semantic analysis beyond host-native skipped mode

## Repository Files

| Path | Purpose |
|------|---------|
| `docs/spec/spec.md` | current complete design |
| `docs/spec/checklist.json` | implementation tracker for this repo |
| `docs/spec/update_history` | append-only design revision log |
| `docs/spec/references.md` | committed reference analysis |
| `src/skill_auditor/` | Python implementation and CLI |
| `tests/` | verification coverage |
| `skills/` | future Codex and Claude wrapper skills |
| `hooks/` | future hook templates and install helpers |
| `.gitignore` | local repo ignore rules, including cloned references |

## Reference Sources

The design is based on these upstream references, cloned locally under `ref/` and ignored from git:

- OpenAI Codex sample skill-creator
- Anthropic skill-creator

The extracted cross-reference notes are committed in `docs/spec/references.md`.

## Privacy and Security Notes

This repository should not commit:

- API keys, tokens, credentials, or private keys
- user-specific secrets or auth material
- local cloned upstream repos under `ref/openai-codex/` and `ref/anthropics-skills/`

Committed content may still mention generic target paths such as `~/.codex/skills` or `~/.claude/skills` because they are part of the product design, not machine-specific secrets.
