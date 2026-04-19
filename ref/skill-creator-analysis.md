# Skill Creator Reference Analysis

This file summarizes the two upstream references cloned into this repo:

- `ref/openai-codex/codex-rs/skills/src/assets/samples/skill-creator/`
- `ref/anthropics-skills/skills/skill-creator/`

The goal is to extract rules that `skill-auditor` can enforce without mixing up:

- hard schema requirements
- recommended structure
- packaging/runtime metadata
- evaluation workflow guidance

## Sources Reviewed

### OpenAI / Codex

- `SKILL.md`
- `scripts/init_skill.py`
- `scripts/quick_validate.py`
- `scripts/generate_openai_yaml.py`
- `references/openai_yaml.md`
- `agents/openai.yaml`

### Anthropic / Claude

- `SKILL.md`
- `scripts/quick_validate.py`
- `scripts/improve_description.py`
- `scripts/package_skill.py`
- `references/schemas.md`

## Shared Rules Across Both References

These are safe candidates for `required.common` or `recommended.common`.

### Hard validation rules

- `SKILL.md` must exist.
- `SKILL.md` must start with YAML frontmatter.
- Frontmatter must parse to a YAML object.
- `name` is required.
- `description` is required.
- `name` must be a string.
- `description` must be a string.
- `name` should be hyphen/kebab-case: lowercase letters, digits, hyphens only.
- `name` cannot start/end with `-` or contain `--`.
- `name` max length is `64`.
- `description` cannot contain `<` or `>`.
- `description` max length is `1024`.

### Shared allowed frontmatter keys

- `name`
- `description`
- `license`
- `allowed-tools`
- `metadata`

### Shared structural guidance

- Skill directory is centered on `SKILL.md`.
- `scripts/`, `references/`, and `assets/` are optional bundled resources.
- Progressive disclosure is expected:
  - metadata decides triggering
  - `SKILL.md` body is loaded after trigger
  - bundled resources are loaded only when needed
- `SKILL.md` should stay lean; both references push toward `< 500` lines.
- Detailed material should move into `references/` instead of bloating `SKILL.md`.

## Codex-Specific Rules

These should **not** be applied to Claude skills as hard failures.

### Extra structure

- `agents/openai.yaml` is recommended, not required.
- `agents/openai.yaml` is UI-facing metadata, not skill logic.

### `agents/openai.yaml` constraints

From `references/openai_yaml.md` and `scripts/generate_openai_yaml.py`:

- Strings should be quoted.
- Keys should stay unquoted.
- `interface.display_name` is human-facing.
- `interface.short_description` must be `25..64` chars.
- `interface.default_prompt` should explicitly mention `$skill-name`.
- Optional UI fields:
  - `icon_small`
  - `icon_large`
  - `brand_color`
- `policy.allow_implicit_invocation` controls implicit triggering.
- `dependencies.tools[]` currently models MCP dependencies.

### Codex-specific audit implications

- Check whether `agents/openai.yaml` exists when the skill appears intended for UI distribution.
- If it exists, validate that:
  - it parses
  - `display_name` and `short_description` are present
  - `short_description` length is valid
  - `default_prompt` mentions `$<skill-name>` when present
  - asset paths referenced by icons exist
- Warn when `openai.yaml` looks stale relative to `SKILL.md` name/description.

## Claude-Specific Rules

These should **not** be treated as universal requirements.

### Extra frontmatter support

- Claude `quick_validate.py` allows one extra top-level key:
  - `compatibility`
- `compatibility` is optional and max length `500`.

### Workflow expectations

Anthropic's reference is much more evaluation-heavy than Codex's sample:

- create realistic eval prompts
- run with-skill and baseline
- grade expectations
- benchmark time/tokens/pass rate
- improve the description based on trigger misses and false triggers
- iterate

### Packaged artifact expectations

From `scripts/package_skill.py`:

- Packaging excludes:
  - `evals/` at the skill root
  - `__pycache__/`
  - `node_modules/`
  - `*.pyc`
  - `.DS_Store`

### Claude-specific audit implications

- `compatibility` is allowed, but optional.
- `evals/evals.json` is strongly recommended for complex objective skills, not universally required.
- A missing eval suite should be a warning/recommendation, not an error.
- Packaging readiness can be checked separately from authoring validity.

## Biggest Philosophy Difference

### Codex reference

- More focused on skill anatomy, progressive disclosure, and clean packaging.
- Stronger emphasis on concise prompts and keeping context small.
- Adds product metadata via `agents/openai.yaml`.

### Anthropic reference

- More focused on iterative evaluation, trigger tuning, and benchmark loops.
- Treats description quality as a measurable optimization problem.
- Provides richer schemas and a packaging workflow.

## What `skill-auditor` Should Enforce

The tool should split findings into layers instead of flattening everything into one lint pass.

### Layer 1: Schema validity

Objective pass/fail checks:

- required files
- frontmatter syntax
- allowed top-level keys by ecosystem
- name and description constraints
- optional metadata shape when present

### Layer 2: Structure quality

Objective or near-objective warnings:

- `SKILL.md` too long
- references/scripts/assets mentioned but missing
- large inlined reference material that should be split out
- presence of extra docs that the Codex sample explicitly discourages

### Layer 3: Trigger quality

Heuristic findings:

- description too generic
- description lacks trigger contexts
- description overfocuses implementation rather than user intent
- likely under-trigger or over-trigger risk
- duplicate or overlapping trigger surface across nearby skills

### Layer 4: Lifecycle quality

Soft checks:

- missing evals for deterministic skills
- missing maintenance record
- stale derived metadata (`openai.yaml`, package manifests, ledger index)
- source provenance missing or weak

## What `skill-auditor` Must Avoid

- Do not mark `agents/openai.yaml` as required for all skills.
- Do not mark `compatibility` as required for Claude skills.
- Do not mark `evals/evals.json` as required for subjective or lightweight skills.
- Do not confuse packaging artifacts with authoring requirements.
- Do not treat stylistic guidance as schema failures.

## Recommended Rule Taxonomy For This Repo

- `required.common`
- `required.codex`
- `required.claude`
- `recommended.common`
- `recommended.codex`
- `recommended.claude`
- `heuristic.trigger`
- `heuristic.overlap`
- `heuristic.smell`

Each finding should carry:

- `rule_id`
- `ecosystem`
- `severity`
- `confidence`
- `path`
- `evidence`
- `suggested_fix`

## Direct Design Consequences For `skill-auditor`

- Keep the rule engine data-driven; do not hardcode all checks in one function.
- Separate scanner output from judgment output.
- Record provenance for every skill:
  - local path
  - ecosystem
  - source type
  - source URL or repo
  - last audited time
  - last changed time
- Model-based clustering or smell review must be optional and clearly labeled as heuristic.
- Static validation must remain deterministic and runnable offline.
