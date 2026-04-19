from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from .models import Finding, SkillInstance
from .utils import tokenize


CATEGORY_RULES: dict[str, tuple[str, ...]] = {
    "documents": (
        "pdf",
        "docx",
        "ppt",
        "pptx",
        "slide",
        "deck",
        "presentation",
        "document",
        "word",
        "report",
    ),
    "finance-spreadsheets": (
        "xlsx",
        "excel",
        "spreadsheet",
        "financial",
        "valuation",
        "dcf",
        "lbo",
        "comps",
        "statement",
        "audit-xls",
    ),
    "design-frontend": (
        "design",
        "frontend",
        "ui",
        "html",
        "css",
        "web",
        "canvas",
        "art",
        "shader",
        "landing",
    ),
    "mobile-dev": (
        "android",
        "ios",
        "flutter",
        "react-native",
        "react native",
        "expo",
        "mobile",
    ),
    "developer-tooling": (
        "plugin",
        "mcp",
        "openai",
        "claude",
        "codex",
        "autoresearch",
        "builder",
        "installer",
        "api",
        "gstack",
    ),
    "media-multimodal": (
        "image",
        "vision",
        "gif",
        "video",
        "music",
        "audio",
        "multimodal",
        "sticker",
    ),
    "web-automation": (
        "web access",
        "scrape",
        "browser",
        "testing",
        "playwright",
        "crawl",
        "automation",
        "dogfood",
    ),
}

TRIGGER_CUE_PATTERNS = (
    "use when",
    "use this when",
    "when users",
    "when user",
    "when asked",
    "whenever",
    "if the user",
    "should be used",
    "trigger",
)
GENERIC_TRIGGER_OPENERS = (
    "guide for",
    "toolkit for",
    "reference for",
    "suite of tools",
    "wrapper for",
    "router for",
)
ACTION_VERBS = {
    "analyze",
    "build",
    "clean",
    "convert",
    "create",
    "edit",
    "extract",
    "fill",
    "generate",
    "make",
    "modify",
    "read",
    "review",
    "test",
    "update",
    "write",
}
STRUCTURED_CATEGORY_LABELS = {
    "documents": "Document workflows",
    "finance-spreadsheets": "Finance and spreadsheet workflows",
    "design-frontend": "Design and frontend",
    "mobile-dev": "Mobile development",
    "developer-tooling": "Developer tooling",
    "media-multimodal": "Media and multimodal",
    "web-automation": "Web automation and testing",
    "general": "General / uncategorized",
}


def build_clusters(instances: list[SkillInstance]) -> dict:
    grouped: dict[str, list[str]] = defaultdict(list)
    for instance in instances:
        grouped[instance.skill_key].append(instance.instance_id)

    clusters = [
        {
            "cluster_id": f"skill-key:{skill_key}",
            "skill_key": skill_key,
            "instance_ids": sorted(instance_ids),
        }
        for skill_key, instance_ids in sorted(grouped.items())
        if len(instance_ids) > 1
    ]
    return {"clusters": clusters}


def classify_instance(instance: SkillInstance) -> dict[str, object]:
    skill_key = instance.skill_key.lower()
    path = Path(instance.path)
    path_text = " ".join(part.lower() for part in path.parts[-2:])
    description = (instance.description or "").lower()
    scores: dict[str, int] = {}
    matched_keywords: dict[str, list[str]] = {}
    for category, keywords in CATEGORY_RULES.items():
        matched = []
        score = 0
        for keyword in keywords:
            keyword_matched = False
            if keyword in skill_key or keyword in path_text:
                score += 2
                keyword_matched = True
            if keyword in description:
                score += 1
                keyword_matched = True
            if keyword_matched:
                matched.append(keyword)
        if matched:
            scores[category] = score
            matched_keywords[category] = matched

    if not scores:
        return {
            "skill_key": instance.skill_key,
            "primary_category": "general",
            "label": STRUCTURED_CATEGORY_LABELS["general"],
            "score": 0,
            "matched_keywords": [],
        }

    primary_category, score = max(scores.items(), key=lambda item: (item[1], item[0]))
    return {
        "skill_key": instance.skill_key,
        "primary_category": primary_category,
        "label": STRUCTURED_CATEGORY_LABELS[primary_category],
        "score": score,
        "matched_keywords": matched_keywords[primary_category],
    }


def build_category_assignments(instances: list[SkillInstance]) -> dict[str, dict[str, object]]:
    return {instance.instance_id: classify_instance(instance) for instance in instances}


def build_overlap_findings(instances: list[SkillInstance]) -> list[Finding]:
    findings: list[Finding] = []
    category_assignments = build_category_assignments(instances)
    sorted_instances = sorted(instances, key=lambda item: (item.skill_key, item.path))
    for left, right in combinations(sorted_instances, 2):
        if left.skill_key == right.skill_key:
            continue
        left_tokens = tokenize(" ".join(filter(None, [left.skill_key, left.description])))
        right_tokens = tokenize(" ".join(filter(None, [right.skill_key, right.description])))
        if not left_tokens or not right_tokens:
            continue
        union = left_tokens | right_tokens
        if not union:
            continue
        similarity = len(left_tokens & right_tokens) / len(union)
        if similarity < 0.42:
            continue
        if (
            category_assignments[left.instance_id]["primary_category"]
            != category_assignments[right.instance_id]["primary_category"]
        ):
            continue
        findings.append(
            Finding(
                rule_id="heuristic.overlap.lexical",
                category="overlap",
                severity="warn",
                confidence=round(similarity, 2),
                ecosystem=left.ecosystem,
                instance_id=left.instance_id,
                path=left.path,
                evidence=(
                    f"Descriptions for {left.skill_key} and {right.skill_key} overlap heavily "
                    f"within category {category_assignments[left.instance_id]['primary_category']} "
                    f"(jaccard={similarity:.2f})."
                ),
                suggested_fix="Clarify trigger boundaries or consolidate overlapping skills.",
            )
        )
    return findings


def build_trigger_findings(instances: list[SkillInstance]) -> list[Finding]:
    findings: list[Finding] = []
    assignments = build_category_assignments(instances)
    for instance in instances:
        description = (instance.description or "").strip()
        lowered = description.lower()
        if not description:
            findings.append(
                Finding(
                    rule_id="heuristic.trigger.missing_description",
                    category="trigger",
                    severity="warn",
                    confidence=0.95,
                    ecosystem=instance.ecosystem,
                    instance_id=instance.instance_id,
                    path=instance.path,
                    evidence="Skill description is empty, so trigger conditions are opaque.",
                    suggested_fix="Add a frontmatter description that explains when the skill should trigger.",
                )
            )
            continue

        has_trigger_cue = any(pattern in lowered for pattern in TRIGGER_CUE_PATTERNS)
        starts_generic = lowered.startswith(GENERIC_TRIGGER_OPENERS)
        action_count = len(tokenize(description) & ACTION_VERBS)
        primary_category = assignments[instance.instance_id]["primary_category"]

        if not has_trigger_cue and starts_generic:
            findings.append(
                Finding(
                    rule_id="heuristic.trigger.missing_activation_cues",
                    category="trigger",
                    severity="warn",
                    confidence=0.72,
                    ecosystem=instance.ecosystem,
                    instance_id=instance.instance_id,
                    path=instance.path,
                    evidence=(
                        f"{instance.skill_key} reads like a generic capability summary without clear "
                        "activation cues such as 'use when' or 'when asked'."
                    ),
                    suggested_fix="Rewrite the description to state when the skill should and should not trigger.",
                )
            )
        elif has_trigger_cue and action_count >= 8 and primary_category == "general":
            findings.append(
                Finding(
                    rule_id="heuristic.trigger.broad_surface",
                    category="trigger",
                    severity="warn",
                    confidence=0.58,
                    ecosystem=instance.ecosystem,
                    instance_id=instance.instance_id,
                    path=instance.path,
                    evidence=(
                        f"{instance.skill_key} exposes a broad action surface without a strong domain anchor; "
                        "it may conflict with neighboring skills."
                    ),
                    suggested_fix="Narrow the trigger text or add explicit exclusions.",
                )
            )
    return findings


def build_redundancy_candidates(instances: list[SkillInstance]) -> list[dict[str, object]]:
    assignments = build_category_assignments(instances)
    candidates: list[dict[str, object]] = []
    for left, right in combinations(sorted(instances, key=lambda item: item.skill_key), 2):
        left_category = assignments[left.instance_id]["primary_category"]
        right_category = assignments[right.instance_id]["primary_category"]
        if left_category != right_category or left_category == "general":
            continue
        left_tokens = tokenize(" ".join(filter(None, [left.skill_key, left.description])))
        right_tokens = tokenize(" ".join(filter(None, [right.skill_key, right.description])))
        if not left_tokens or not right_tokens:
            continue
        union = left_tokens | right_tokens
        similarity = len(left_tokens & right_tokens) / len(union)
        shared_anchor_tokens = {
            token
            for token in (tokenize(left.skill_key) & tokenize(right.skill_key))
            if len(token) >= 4
        }
        if similarity < 0.22 and not shared_anchor_tokens:
            continue
        candidates.append(
            {
                "skill_keys": [left.skill_key, right.skill_key],
                "category": left_category,
                "similarity": round(similarity, 2),
                "reason": (
                    f"Shared category {left_category} with lexical similarity {similarity:.2f}; "
                    + (
                        f"shared anchors: {', '.join(sorted(shared_anchor_tokens))}. "
                        if shared_anchor_tokens
                        else ""
                    )
                    + "review for redundancy or trigger conflict."
                ),
            }
        )
    return sorted(candidates, key=lambda item: (-item["similarity"], item["skill_keys"]))


def build_validity_summary(
    instances: list[SkillInstance],
    deterministic_findings: list[Finding],
    heuristic_findings: list[Finding],
) -> dict[str, object]:
    deterministic_by_instance: dict[str, list[Finding]] = defaultdict(list)
    heuristic_by_instance: dict[str, list[Finding]] = defaultdict(list)
    for finding in deterministic_findings:
        deterministic_by_instance[finding.instance_id].append(finding)
    for finding in heuristic_findings:
        heuristic_by_instance[finding.instance_id].append(finding)

    counts = Counter()
    skill_states: list[dict[str, object]] = []
    for instance in instances:
        det = deterministic_by_instance.get(instance.instance_id, [])
        heu = heuristic_by_instance.get(instance.instance_id, [])
        if any(finding.severity == "error" for finding in det):
            status = "invalid"
        elif det or heu:
            status = "review"
        else:
            status = "ready"
        counts[status] += 1
        skill_states.append(
            {
                "skill_key": instance.skill_key,
                "status": status,
                "deterministic_count": len(det),
                "heuristic_count": len(heu),
            }
        )
    return {
        "counts": {
            "ready": counts["ready"],
            "review": counts["review"],
            "invalid": counts["invalid"],
        },
        "skills": sorted(skill_states, key=lambda item: (item["status"], item["skill_key"])),
    }


def build_category_summary(instances: list[SkillInstance]) -> dict[str, object]:
    assignments = build_category_assignments(instances)
    grouped: dict[str, list[str]] = defaultdict(list)
    for instance in instances:
        category = assignments[instance.instance_id]["primary_category"]
        grouped[category].append(instance.skill_key)
    counts = {
        category: len(skill_keys)
        for category, skill_keys in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
    }
    return {
        "counts": counts,
        "assignments": assignments,
    }


def build_trigger_summary(instances: list[SkillInstance], heuristic_findings: list[Finding]) -> dict[str, object]:
    cue_missing = [
        finding for finding in heuristic_findings if finding.rule_id == "heuristic.trigger.missing_activation_cues"
    ]
    broad_surface = [
        finding for finding in heuristic_findings if finding.rule_id == "heuristic.trigger.broad_surface"
    ]
    with_descriptions = [instance for instance in instances if instance.description]
    descriptions_with_cues = [
        instance
        for instance in with_descriptions
        if any(pattern in instance.description.lower() for pattern in TRIGGER_CUE_PATTERNS)
    ]
    return {
        "described_skills": len(with_descriptions),
        "cue_coverage": round(
            len(descriptions_with_cues) / len(with_descriptions), 2
        )
        if with_descriptions
        else 0.0,
        "missing_activation_cues": len(cue_missing),
        "broad_surface_candidates": len(broad_surface),
    }


def build_active_set(
    instances: list[SkillInstance],
    deterministic_findings: list[Finding],
    heuristic_findings: list[Finding],
    *,
    max_items: int,
) -> dict:
    category_summary = build_category_summary(instances)
    redundancy_candidates = build_redundancy_candidates(instances)
    blocked_ids = {
        finding.instance_id
        for finding in deterministic_findings
        if finding.severity == "error"
    }
    warning_counts: dict[str, int] = defaultdict(int)
    for finding in deterministic_findings:
        if finding.severity == "warn":
            warning_counts[finding.instance_id] += 1
    heuristic_counts: dict[str, int] = defaultdict(int)
    for finding in heuristic_findings:
        heuristic_counts[finding.instance_id] += 1

    redundancy_penalty: dict[str, int] = defaultdict(int)
    skill_key_to_instance_ids: dict[str, list[str]] = defaultdict(list)
    for instance in instances:
        skill_key_to_instance_ids[instance.skill_key].append(instance.instance_id)
    for candidate in redundancy_candidates:
        for skill_key in candidate["skill_keys"]:
            for instance_id in skill_key_to_instance_ids.get(skill_key, []):
                redundancy_penalty[instance_id] += 1

    eligible = [instance for instance in instances if instance.instance_id not in blocked_ids]
    assignments = category_summary["assignments"]
    selected: list[SkillInstance] = []
    remaining = eligible[:]
    category_counts: dict[str, int] = defaultdict(int)
    selected_skill_keys: set[str] = set()

    while remaining and len(selected) < max_items:
        remaining.sort(
            key=lambda item: (
                warning_counts[item.instance_id],
                heuristic_counts[item.instance_id],
                category_counts[assignments[item.instance_id]["primary_category"]],
                redundancy_penalty[item.instance_id],
                item.skill_key,
                item.path,
            )
        )
        chosen = None
        for candidate in remaining:
            if _would_duplicate_redundant_family(candidate, selected_skill_keys, redundancy_candidates):
                continue
            chosen = candidate
            break
        if chosen is None:
            chosen = remaining[0]
        remaining.remove(chosen)
        selected.append(chosen)
        selected_skill_keys.add(chosen.skill_key)
        category_counts[assignments[chosen.instance_id]["primary_category"]] += 1

    recommended = [
        {
            "instance_id": instance.instance_id,
            "skill_key": instance.skill_key,
            "path": instance.path,
            "category": assignments[instance.instance_id]["label"],
            "warning_count": warning_counts[instance.instance_id],
            "heuristic_count": heuristic_counts[instance.instance_id],
            "redundancy_penalty": redundancy_penalty[instance.instance_id],
            "score": _active_score(
                repo_category_count=category_summary["counts"].get(assignments[instance.instance_id]["primary_category"], 0),
                warning_count=warning_counts[instance.instance_id],
                heuristic_count=heuristic_counts[instance.instance_id],
                redundancy_penalty=redundancy_penalty[instance.instance_id],
            ),
            "reasons": _active_reasons(
                category_label=assignments[instance.instance_id]["label"],
                repo_category_count=category_summary["counts"].get(assignments[instance.instance_id]["primary_category"], 0),
                warning_count=warning_counts[instance.instance_id],
                heuristic_count=heuristic_counts[instance.instance_id],
                redundancy_penalty=redundancy_penalty[instance.instance_id],
            ),
        }
        for instance in selected
    ]
    return {"max": max_items, "recommended_active": recommended}


def build_governance_actions(
    instances: list[SkillInstance],
    deterministic_findings: list[Finding],
    heuristic_findings: list[Finding],
) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    validity = build_validity_summary(instances, deterministic_findings, heuristic_findings)
    redundancy_candidates = build_redundancy_candidates(instances)
    trigger_summary = build_trigger_summary(instances, heuristic_findings)
    category_summary = build_category_summary(instances)

    invalid_skills = [item["skill_key"] for item in validity["skills"] if item["status"] == "invalid"][:10]
    if invalid_skills:
        actions.append(
            {
                "type": "invalid-repair",
                "priority": "high",
                "title": "Repair invalid skills before expanding active use",
                "details": f"{len(invalid_skills)} skills are invalid under deterministic checks.",
                "skill_keys": invalid_skills,
            }
        )

    if redundancy_candidates:
        top = redundancy_candidates[0]
        actions.append(
            {
                "type": "redundancy-review",
                "priority": "medium",
                "title": "Review redundant or family-overlapping skills",
                "details": top["reason"],
                "skill_keys": top["skill_keys"],
            }
        )

    trigger_cleanup_skills = [
        instance.skill_key
        for instance in instances
        if any(
            finding.instance_id == instance.instance_id and finding.rule_id.startswith("heuristic.trigger.")
            for finding in heuristic_findings
        )
    ]
    if trigger_cleanup_skills:
        actions.append(
            {
                "type": "trigger-cleanup",
                "priority": "medium",
                "title": "Tighten trigger descriptions with weak activation cues",
                "details": (
                    f"{trigger_summary['missing_activation_cues']} descriptions lack clear 'use when' style activation cues."
                ),
                "skill_keys": trigger_cleanup_skills[:10],
            }
        )

    saturated_categories = [
        (category, count)
        for category, count in category_summary["counts"].items()
        if count >= 8
    ]
    if saturated_categories:
        category, count = saturated_categories[0]
        actions.append(
            {
                "type": "category-trim",
                "priority": "medium",
                "title": "Review saturated categories for active-set trimming",
                "details": f"Category {category} currently contains {count} skills.",
                "skill_keys": [],
            }
        )
    return actions


def build_remediation_suggestions(
    instances: list[SkillInstance],
    deterministic_findings: list[Finding],
    heuristic_findings: list[Finding],
) -> list[dict[str, object]]:
    instance_map = {instance.instance_id: instance for instance in instances}
    findings_by_instance: dict[str, list[Finding]] = defaultdict(list)
    for finding in deterministic_findings + heuristic_findings:
        findings_by_instance[finding.instance_id].append(finding)

    suggestions: list[dict[str, object]] = []
    for instance in instances:
        findings = findings_by_instance.get(instance.instance_id, [])
        if not findings:
            continue
        findings = sorted(findings, key=lambda item: (item.severity != "error", item.rule_id))
        primary = findings[0]
        remediation = _remediation_text(instance, primary)
        suggestions.append(
            {
                "skill_key": instance.skill_key,
                "status": "invalid" if any(f.severity == "error" for f in findings) else "review",
                "issues": [finding.rule_id for finding in findings[:3]],
                "what": remediation["what"],
                "how": remediation["how"],
            }
        )
    suggestions.sort(key=lambda item: (item["status"] != "invalid", item["skill_key"]))
    return suggestions[:12]


def build_priority_actions(
    instances: list[SkillInstance],
    deterministic_findings: list[Finding],
    heuristic_findings: list[Finding],
) -> list[dict[str, object]]:
    instance_map = {instance.instance_id: instance for instance in instances}
    findings_by_instance: dict[str, list[Finding]] = defaultdict(list)
    for finding in deterministic_findings + heuristic_findings:
        findings_by_instance[finding.instance_id].append(finding)

    actions: list[dict[str, object]] = []

    security_invalid = [
        instance_map[finding.instance_id].skill_key
        for finding in deterministic_findings
        if finding.rule_id in {"security.binary.opaque_execution", "security.shell.pipe_to_shell"}
    ]
    if security_invalid:
        actions.append(
            {
                "priority": "P0",
                "what": "Remove unsafe execution patterns from installed skills",
                "why": "These are real blocking findings that still deserve hard attention even after metadata debt was downgraded.",
                "which": sorted(set(security_invalid)),
                "how": (
                    "Inspect each flagged script, replace temp/download execution or pipe-to-shell flows with committed reviewable scripts, "
                    "then rerun `skill-auditor audit` to confirm the error is gone."
                ),
            }
        )

    redundancy_candidates = build_redundancy_candidates(instances)
    if redundancy_candidates:
        top = redundancy_candidates[0]
        actions.append(
            {
                "priority": "P1",
                "what": "Trim redundant family skills before they compete for the same trigger surface",
                "why": "Redundant design-family skills create trigger noise and make active-set curation harder.",
                "which": top["skill_keys"],
                "how": (
                    "Review the pair side-by-side, decide whether one should be canonical, whether one should narrow its trigger wording, "
                    "or whether both should stay but with explicit family boundaries."
                ),
            }
        )

    weak_trigger_skills = [
        instance_map[finding.instance_id].skill_key
        for finding in heuristic_findings
        if finding.rule_id.startswith("heuristic.trigger.")
    ]
    if weak_trigger_skills:
        actions.append(
            {
                "priority": "P1",
                "what": "Rewrite weak trigger descriptions into explicit activation rules",
                "why": "Descriptions without clear `use when` cues are hard to route correctly and often cause under-trigger or over-trigger behavior.",
                "which": sorted(set(weak_trigger_skills)),
                "how": (
                    "For each skill, rewrite the frontmatter description to explicitly state when it should trigger, when it should not trigger, "
                    "and which neighboring skills it should defer to."
                ),
            }
        )

    lifecycle_review = [
        instance_map[finding.instance_id].skill_key
        for finding in deterministic_findings
        if finding.rule_id.startswith("codex.openai_yaml.") or finding.rule_id == "structure.skill_md.too_long"
    ]
    if lifecycle_review:
        actions.append(
            {
                "priority": "P2",
                "what": "Batch UI metadata polish and oversized SKILL.md cleanup separately from blocking work",
                "why": "These items hurt maintainability and presentation, but they are mostly review-only debt and should not outrank true security or trigger issues.",
                "which": sorted(set(lifecycle_review))[:12],
                "how": (
                    "Split bulky SKILL.md files into references/, and only fix openai.yaml fields for skills that truly need polished Codex UI surfaces."
                ),
            }
        )

    return actions


def _would_duplicate_redundant_family(
    candidate: SkillInstance,
    selected_skill_keys: set[str],
    redundancy_candidates: list[dict[str, object]],
) -> bool:
    for redundancy_candidate in redundancy_candidates:
        pair = set(redundancy_candidate["skill_keys"])
        if candidate.skill_key in pair and pair & selected_skill_keys:
            return True
    return False


def _active_score(
    *,
    repo_category_count: int,
    warning_count: int,
    heuristic_count: int,
    redundancy_penalty: int,
) -> int:
    score = 100
    score -= max(repo_category_count - 1, 0)
    score -= warning_count * 8
    score -= heuristic_count * 6
    score -= redundancy_penalty * 10
    return max(score, 0)


def _active_reasons(
    *,
    category_label: str,
    repo_category_count: int,
    warning_count: int,
    heuristic_count: int,
    redundancy_penalty: int,
) -> list[str]:
    reasons = [f"covers {category_label}"]
    if repo_category_count <= 4:
        reasons.append("category is relatively scarce")
    elif repo_category_count >= 12:
        reasons.append("selected despite a saturated category")
    if warning_count == 0:
        reasons.append("no deterministic warnings")
    if heuristic_count == 0:
        reasons.append("no heuristic debt")
    if redundancy_penalty == 0:
        reasons.append("not currently in a redundant family")
    return reasons


def _remediation_text(instance: SkillInstance, finding: Finding) -> dict[str, str]:
    path = finding.path
    loc = f"L{finding.line_number}" if finding.line_number else None
    snippet = f"`{finding.matched_text}`" if finding.matched_text else None
    loc_ref = f"{path} {loc}" if loc else path

    if finding.rule_id == "security.shell.pipe_to_shell":
        detail = f"在 {loc_ref} 发现 {snippet} — curl/wget 输出直接管道到 shell 解释器。" if snippet else f"在 {loc_ref} 发现 pipe-to-shell 模式。"
        return {
            "what": "移除 pipe-to-shell 安装流程",
            "how": (
                f"{detail} "
                "替换方案：(1) 将安装脚本提交到 `scripts/install.sh` 并经过 review；"
                "(2) 改用 `bash scripts/install.sh` 调用；"
                "(3) 重新运行 `skill-auditor audit` 确认 error 消失。"
            ),
        }

    if finding.rule_id == "security.binary.opaque_execution":
        detail = f"在 {loc_ref} 发现 {snippet} — 直接执行临时目录/下载目录中的二进制。" if snippet else f"在 {loc_ref} 发现不透明二进制执行。"
        return {
            "what": "替换不透明二进制执行路径",
            "how": (
                f"{detail} "
                "替换方案：(1) 将安装/执行逻辑提交为可 review 的 wrapper 脚本；"
                "(2) 确保二进制路径在受控位置（项目目录或包管理器路径）而不是 /tmp 或 Downloads；"
                "(3) 重新运行 `skill-auditor audit` 确认 error 消失。"
            ),
        }

    if finding.rule_id.startswith("security.secret."):
        detail = f"在 {loc_ref} 发现 {snippet}。" if snippet else f"在 {loc_ref} 发现疑似密钥内容。"
        return {
            "what": "移除硬编码密钥材料",
            "how": (
                f"{detail} "
                "替换方案：(1) 删除该行；(2) 如需配置，改用环境变量或外部配置文件；"
                "(3) 确认该密钥未提交到 git 历史（如有必要，用 git filter-repo 清理）。"
            ),
        }

    if finding.rule_id.startswith("codex.openai_yaml."):
        return {
            "what": "修复 openai.yaml UI 元数据字段",
            "how": (
                f"在 {path} — {finding.evidence} "
                "此问题属于可选 UI 元数据 debt，不影响 skill 核心功能；"
                "仅在需要 Codex UI 界面精良呈现时才修复。"
            ),
        }

    if finding.rule_id == "schema.frontmatter.unexpected_key":
        return {
            "what": "清理 frontmatter 多余字段",
            "how": (
                f"在 {path} — {finding.evidence} "
                "将多余字段移入 `metadata:` 下作为扩展信息，或在团队策略中明确 allowlist，避免解析器警告。"
            ),
        }

    if finding.rule_id == "structure.skill_md.too_long":
        return {
            "what": "拆分过长的 SKILL.md",
            "how": (
                f"{path} 当前 {finding.evidence.split()[2]} 行（建议 500 行以内）。"
                "拆分方案：(1) 将参考文档、示例、详细 API 说明移到 `references/` 目录；"
                "(2) SKILL.md 只保留触发条件、核心工作流、关键决策点；"
                "(3) 用相对链接指向 references/ 内容。"
            ),
        }

    if finding.rule_id.startswith("heuristic.trigger."):
        return {
            "what": "将触发描述改写为明确激活规则",
            "how": (
                f"在 {path} frontmatter description — {finding.evidence} "
                "改写要点：(1) 开头用 'Use when...' 或 'When user asks...' 明确触发场景；"
                "(2) 加一句 'Do NOT use when...' 列举不应触发的场景；"
                "(3) 点名 1-2 个相邻 skill，说明与它们的边界。"
            ),
        }

    return {
        "what": f"修复 {finding.rule_id}",
        "how": (
            f"在 {loc_ref} — {finding.evidence} "
            f"{finding.suggested_fix or '按规则说明修复后重新运行 audit 确认。'}"
        ),
    }
