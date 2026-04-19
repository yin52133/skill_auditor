from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict

from .analysis import (
    STRUCTURED_CATEGORY_LABELS,
    build_active_set,
    build_category_summary,
    build_governance_actions,
    build_priority_actions,
    build_redundancy_candidates,
    build_remediation_suggestions,
    build_trigger_summary,
    build_validity_summary,
)
from .models import AuditReport


TRANSLATIONS = {
    "en": {
        "title": "skill-auditor report",
        "executive_summary": "Executive Summary",
        "validity_summary": "Validity Summary",
        "severity_summary": "Severity Summary",
        "category_summary": "Category Summary",
        "trigger_quality_summary": "Trigger Quality Summary",
        "priority_overview": "Priority Overview",
        "priority_actions": "Priority Actions",
        "rule_summary": "Rule Summary",
        "redundancy_candidates": "Redundancy Candidates",
        "conflict_candidates": "Conflict Candidates",
        "most_impacted_skills": "Most Impacted Skills",
        "false_positive_candidates": "False Positive Candidates",
        "governance_actions": "Governance Actions",
        "active_set_recommendation": "Active Set Recommendation",
        "concrete_remediation": "Concrete Remediation Suggestions",
        "hook_strategy": "Hook Strategy",
        "recommended_actions": "Recommended Actions",
        "instances": "Instances",
        "deterministic_findings": "Deterministic Findings",
        "heuristic_findings": "Heuristic Findings",
        "scanned": "Scanned",
        "skill_instances": "skill instances",
        "for_ecosystem": "for ecosystem",
        "semantic_status": "Semantic status",
        "description_cue_coverage": "Description cue coverage",
        "missing_activation_cues": "Missing activation cues",
        "broad_trigger_surface_candidates": "Broad trigger surface candidates",
        "heuristic_rules": "Heuristic rules",
        "no_rules": "No deterministic rules fired.",
        "no_redundancy": "No strong redundancy candidates were detected.",
        "no_conflicts": "No obvious trigger conflicts were detected.",
        "no_impacted": "No impacted skills.",
        "no_false_positives": "No obvious false-positive candidates were detected.",
        "no_governance_actions": "No governance actions were generated.",
        "manual_trigger": "Manual trigger: run `skill-auditor audit` in the foreground for review-quality reports.",
        "hook_gate": "Repo-local hook gate: use `skill-auditor hook-run` from git hooks to block deterministic errors only.",
        "continuous_scan": "Continuous scanning: use `skill-auditor watch` as the background path when you own the source repo.",
        "false_positive_suffix": "(false-positive candidate; review before treating as a true violation)",
        "status_ready": "ready",
        "status_review": "review",
        "status_invalid": "invalid",
        "priority_high": "high",
        "priority_medium": "medium",
        "warnings": "warnings",
        "heuristics": "heuristics",
        "redundancy_penalty": "redundancy_penalty",
        "score": "score",
        "reasons": "reasons",
        "issues": "issues",
        "suggestion": "suggestion",
        "what": "What",
        "why": "Why",
        "which": "Which",
        "how": "How",
    },
    "zh": {
        "title": "skill-auditor 审计报告",
        "executive_summary": "总体摘要",
        "validity_summary": "有效性摘要",
        "severity_summary": "严重级别摘要",
        "category_summary": "分类摘要",
        "trigger_quality_summary": "触发条件质量摘要",
        "priority_overview": "优先级概览",
        "priority_actions": "优先级动作",
        "rule_summary": "规则摘要",
        "redundancy_candidates": "冗余候选",
        "conflict_candidates": "冲突候选",
        "most_impacted_skills": "受影响最重的 Skills",
        "false_positive_candidates": "疑似误报候选",
        "governance_actions": "治理动作",
        "active_set_recommendation": "Active Set 推荐",
        "concrete_remediation": "具体整改建议",
        "hook_strategy": "Hook 策略",
        "recommended_actions": "建议动作",
        "instances": "实例列表",
        "deterministic_findings": "确定性发现",
        "heuristic_findings": "启发式发现",
        "scanned": "扫描了",
        "skill_instances": "个 skill 实例",
        "for_ecosystem": "生态",
        "semantic_status": "语义分析状态",
        "description_cue_coverage": "描述中触发提示覆盖率",
        "missing_activation_cues": "缺少激活提示的数量",
        "broad_trigger_surface_candidates": "触发面过宽候选",
        "heuristic_rules": "启发式规则",
        "no_rules": "没有触发确定性规则。",
        "no_redundancy": "没有检测到强冗余候选。",
        "no_conflicts": "没有检测到明显触发冲突。",
        "no_impacted": "没有高影响 skill。",
        "no_false_positives": "没有明显的误报候选。",
        "no_governance_actions": "没有生成治理动作。",
        "manual_trigger": "主动触发：前台运行 `skill-auditor audit`，适合人工 review 报告。",
        "hook_gate": "仓库级 hook gate：通过 git hooks 调用 `skill-auditor hook-run`，只阻断确定性错误。",
        "continuous_scan": "持续扫描：在你拥有源码仓库时，后台使用 `skill-auditor watch`。",
        "false_positive_suffix": "（疑似误报，先人工复核再当成真实违规）",
        "status_ready": "可用",
        "status_review": "待复核",
        "status_invalid": "无效",
        "priority_high": "高",
        "priority_medium": "中",
        "warnings": "warnings",
        "heuristics": "heuristics",
        "redundancy_penalty": "redundancy_penalty",
        "score": "分数",
        "reasons": "理由",
        "issues": "问题",
        "suggestion": "建议",
        "what": "做什么",
        "why": "为什么",
        "which": "涉及哪些",
        "how": "怎么做",
    },
}


def render_report(report: AuditReport, output_format: str, *, language: str = "en") -> str:
    if output_format == "json":
        return render_json(report)
    if output_format == "markdown":
        return render_markdown(report, language=language)
    return render_text(report, language=language)


def render_json(report: AuditReport) -> str:
    payload = {
        "run_id": report.run_id,
        "status": report.status,
        "target_scope": report.target_scope,
        "instances": [asdict(instance) for instance in report.instances],
        "deterministic_findings": [asdict(finding) for finding in report.deterministic_findings],
        "heuristic_findings": [asdict(finding) for finding in report.heuristic_findings],
        "summary": build_report_summary(report),
        "semantic_status": report.semantic_status,
        "started_at": report.started_at,
        "finished_at": report.finished_at,
    }
    return json.dumps(payload, indent=2)


def render_text(report: AuditReport, *, language: str = "en") -> str:
    t = TRANSLATIONS[language]
    lines = [
        f"run_id: {report.run_id}",
        f"instances: {len(report.instances)}",
        f"deterministic_findings: {len(report.deterministic_findings)}",
        f"heuristic_findings: {len(report.heuristic_findings)}",
        f"semantic_status: {report.semantic_status}",
    ]
    for instance in report.instances:
        lines.append(f"- {instance.skill_key} [{instance.ecosystem}] {instance.path}")
    for finding in report.deterministic_findings + report.heuristic_findings:
        lines.append(f"* {finding.severity} {finding.rule_id}: {finding.evidence}")
    if language == "zh":
        lines.insert(0, f"{t['title']}: {report.run_id}")
    return "\n".join(lines)


def render_markdown(report: AuditReport, *, language: str = "en") -> str:
    t = TRANSLATIONS[language]
    summary = build_report_summary(report)
    active_set = build_active_set(
        report.instances,
        report.deterministic_findings,
        report.heuristic_findings,
        max_items=min(10, max(1, len(report.instances))),
    )
    severity_counts = Counter(finding.severity for finding in report.deterministic_findings)
    deterministic_rule_counts = Counter(finding.rule_id for finding in report.deterministic_findings)
    heuristic_rule_counts = Counter(finding.rule_id for finding in report.heuristic_findings)
    instance_map = {instance.instance_id: instance for instance in report.instances}
    findings_by_instance: dict[str, list] = defaultdict(list)
    for finding in report.deterministic_findings:
        findings_by_instance[finding.instance_id].append(finding)
    top_impacted = sorted(
        findings_by_instance.items(),
        key=lambda item: (-len(item[1]), instance_map[item[0]].skill_key if item[0] in instance_map else item[0]),
    )[:10]
    false_positive_candidates = [
        finding for finding in report.deterministic_findings if _is_false_positive_candidate(finding)
    ]

    lines = [
        f"# {t['title']} `{report.run_id}`",
        "",
        f"## {t['executive_summary']}",
        f"- {t['scanned']} `{len(report.instances)}` {t['skill_instances']}，{t['for_ecosystem']} `{report.target_scope.get('ecosystem', 'unknown')}`。"
        if language == "zh"
        else f"- Scanned `{len(report.instances)}` skill instances for ecosystem `{report.target_scope.get('ecosystem', 'unknown')}`.",
        f"- {'确定性发现' if language == 'zh' else 'Deterministic findings'}: `{len(report.deterministic_findings)}`.",
        f"- {'启发式发现' if language == 'zh' else 'Heuristic findings'}: `{len(report.heuristic_findings)}`.",
        f"- {t['semantic_status']}: `{report.semantic_status}`.",
        "",
        f"## {t['validity_summary']}",
        f"- `{t['status_ready']}`: `{summary['validity']['counts']['ready']}`",
        f"- `{t['status_review']}`: `{summary['validity']['counts']['review']}`",
        f"- `{t['status_invalid']}`: `{summary['validity']['counts']['invalid']}`",
        "",
        f"## {t['severity_summary']}",
        f"- `error`: `{severity_counts.get('error', 0)}`",
        f"- `warn`: `{severity_counts.get('warn', 0)}`",
        f"- `info`: `{severity_counts.get('info', 0)}`",
        "",
        f"## {t['category_summary']}",
    ]
    for category, count in summary["categories"]["counts"].items():
        label = STRUCTURED_CATEGORY_LABELS.get(category, category)
        if language == "zh":
            label = _translate_category(label)
        lines.append(f"- `{label}`: `{count}`")

    lines.extend(["", f"## {t['trigger_quality_summary']}"])
    lines.append(f"- {t['description_cue_coverage']}: `{summary['trigger_quality']['cue_coverage']}`")
    lines.append(f"- {t['missing_activation_cues']}: `{summary['trigger_quality']['missing_activation_cues']}`")
    lines.append(f"- {t['broad_trigger_surface_candidates']}: `{summary['trigger_quality']['broad_surface_candidates']}`")

    lines.extend(["", f"## {t['priority_overview']}"])
    priority_counts = Counter(action["priority"] for action in summary["priority_actions"])
    for key in ("P0", "P1", "P2"):
        lines.append(f"- `{key}`: `{priority_counts.get(key, 0)}`")

    lines.extend(["", f"## {t['rule_summary']}"])
    if deterministic_rule_counts:
        lines.extend(f"- `{rule_id}`: `{count}`" for rule_id, count in deterministic_rule_counts.most_common(10))
    else:
        lines.append(f"- {t['no_rules']}")
    if heuristic_rule_counts:
        lines.append(f"- {t['heuristic_rules']}:")
        lines.extend(f"  - `{rule_id}`: `{count}`" for rule_id, count in heuristic_rule_counts.most_common(10))

    lines.extend(["", f"## {t['redundancy_candidates']}"])
    if summary["redundancy_candidates"]:
        for candidate in summary["redundancy_candidates"][:10]:
            left, right = candidate["skill_keys"]
            reason = _zh_redundancy_reason(candidate["reason"]) if language == "zh" else candidate["reason"]
            cat = _translate_category(STRUCTURED_CATEGORY_LABELS.get(candidate["category"], candidate["category"])) if language == "zh" else candidate["category"]
            lines.append(
                f"- `{left}` vs `{right}` [{cat}] "
                f"(相似度 `{candidate['similarity']}`): {reason}"
                if language == "zh"
                else f"- `{left}` vs `{right}` in `{candidate['category']}` "
                f"(similarity `{candidate['similarity']}`): {candidate['reason']}"
            )
    else:
        lines.append(f"- {t['no_redundancy']}")

    lines.extend(["", f"## {t['conflict_candidates']}"])
    conflict_candidates = [finding for finding in report.heuristic_findings if finding.rule_id == "heuristic.overlap.lexical"]
    if conflict_candidates:
        for finding in conflict_candidates[:10]:
            lines.append(f"- `{finding.rule_id}`: {finding.evidence}")
    else:
        lines.append(f"- {t['no_conflicts']}")

    lines.extend(["", f"## {t['most_impacted_skills']}"])
    if top_impacted:
        for instance_id, findings in top_impacted:
            instance = instance_map[instance_id]
            top_rules = Counter(finding.rule_id for finding in findings).most_common(3)
            rule_summary = ", ".join(f"{rule_id} x{count}" for rule_id, count in top_rules)
            category = summary["categories"]["assignments"][instance_id]["label"]
            if language == "zh":
                category = _translate_category(category)
            lines.append(
                f"- `{instance.skill_key}` [{category}]: `{len(findings)}` {'条确定性发现' if language == 'zh' else 'deterministic findings'}"
                + (f" ({rule_summary})" if rule_summary else "")
            )
    else:
        lines.append(f"- {t['no_impacted']}")

    lines.extend(["", f"## {t['false_positive_candidates']}"])
    if false_positive_candidates:
        for finding in false_positive_candidates[:10]:
            instance = instance_map.get(finding.instance_id)
            skill_key = instance.skill_key if instance else finding.instance_id
            lines.append(
                f"- `{skill_key}` `{finding.rule_id}`: {finding.evidence} {t['false_positive_suffix']}"
            )
    else:
        lines.append(f"- {t['no_false_positives']}")

    lines.extend(["", f"## {t['governance_actions']}"])
    if summary["governance_actions"]:
        for action in summary["governance_actions"]:
            priority = t[f"priority_{action['priority']}"]
            suffix = f" 涉及: {', '.join(action['skill_keys'])}." if action["skill_keys"] else ""
            if language == "zh":
                zh_title, zh_details = _zh_governance_action(action)
                lines.append(f"- `{priority}` `{action['type']}`: {zh_title}。{zh_details}{suffix}")
            else:
                suffix_en = f" Skills: {', '.join(action['skill_keys'])}." if action["skill_keys"] else ""
                lines.append(f"- `{priority}` `{action['type']}`: {action['title']}. {action['details']}{suffix_en}")
    else:
        lines.append(f"- {t['no_governance_actions']}")

    lines.extend(["", f"## {t['priority_actions']}"])
    for action in summary["priority_actions"]:
        which = ", ".join(action["which"]) if action["which"] else "-"
        if language == "zh":
            what_zh = _PRIORITY_WHAT_ZH.get(action["what"], action["what"])
            why_zh = _PRIORITY_WHY_ZH.get(action["why"], action["why"])
            how_zh = _PRIORITY_HOW_ZH.get(action["how"], action["how"])
            lines.append(f"- `{action['priority']}` {t['what']}: {what_zh}")
            lines.append(f"  {t['why']}: {why_zh}")
            lines.append(f"  {t['which']}: {which}")
            lines.append(f"  {t['how']}: {how_zh}")
        else:
            lines.append(f"- `{action['priority']}` {t['what']}: {action['what']}")
            lines.append(f"  {t['why']}: {action['why']}")
            lines.append(f"  {t['which']}: {which}")
            lines.append(f"  {t['how']}: {action['how']}")

    lines.extend(["", f"## {t['active_set_recommendation']}"])
    for entry in active_set["recommended_active"]:
        category = entry["category"]
        if language == "zh":
            category = _translate_category(category)
            reasons = "；".join(_zh_active_reason(r) for r in entry["reasons"])
        else:
            reasons = "; ".join(entry["reasons"])
        lines.append(
            f"- `{entry['skill_key']}` [{category}] {t['score']}={entry['score']} "
            f"{t['warnings']}={entry['warning_count']} {t['heuristics']}={entry['heuristic_count']} "
            f"{t['redundancy_penalty']}={entry['redundancy_penalty']} {t['reasons']}: {reasons}"
        )

    lines.extend(["", f"## {t['concrete_remediation']}"])
    for suggestion in summary["remediation_suggestions"]:
        status = t["status_invalid"] if suggestion["status"] == "invalid" else t["status_review"]
        issues = ", ".join(suggestion["issues"])
        lines.append(f"- `{suggestion['skill_key']}` [{status}]")
        lines.append(f"  {t['issues']}: {issues}")
        lines.append(f"  {t['what']}: {suggestion['what']}")
        lines.append(f"  {t['why']}: {_remediation_why(suggestion['status'], language)}")
        lines.append(f"  {t['which']}: {suggestion['skill_key']}")
        lines.append(f"  {t['how']}: {suggestion['how']}")

    lines.extend(
        [
            "",
            f"## {t['hook_strategy']}",
            f"- {t['manual_trigger']}",
            f"- {t['hook_gate']}",
            f"- {t['continuous_scan']}",
            "",
            f"## {t['recommended_actions']}",
        ]
    )
    for recommendation in _build_recommendations(report, summary, false_positive_candidates, language=language):
        lines.append(f"- {recommendation}")

    lines.extend(["", f"## {t['instances']}"])
    for instance in report.instances:
        category = summary["categories"]["assignments"][instance.instance_id]["label"]
        if language == "zh":
            category = _translate_category(category)
        lines.append(f"- `{instance.skill_key}` ({instance.ecosystem}, {category}) - `{instance.path}`")
    if report.deterministic_findings:
        lines.extend(["", f"## {t['deterministic_findings']}"])
        lines.extend(
            f"- `{finding.severity}` `{finding.rule_id}`: {finding.evidence}"
            for finding in report.deterministic_findings
        )
    if report.heuristic_findings:
        lines.extend(["", f"## {t['heuristic_findings']}"])
        lines.extend(
            f"- `{finding.severity}` `{finding.rule_id}`: {finding.evidence}"
            for finding in report.heuristic_findings
        )
    return "\n".join(lines)


def build_report_summary(report: AuditReport) -> dict[str, object]:
    validity = build_validity_summary(report.instances, report.deterministic_findings, report.heuristic_findings)
    categories = build_category_summary(report.instances)
    trigger_quality = build_trigger_summary(report.instances, report.heuristic_findings)
    redundancy_candidates = build_redundancy_candidates(report.instances)
    governance_actions = build_governance_actions(
        report.instances,
        report.deterministic_findings,
        report.heuristic_findings,
    )
    priority_actions = build_priority_actions(
        report.instances,
        report.deterministic_findings,
        report.heuristic_findings,
    )
    remediation_suggestions = build_remediation_suggestions(
        report.instances,
        report.deterministic_findings,
        report.heuristic_findings,
    )
    return {
        "validity": validity,
        "categories": categories,
        "trigger_quality": trigger_quality,
        "redundancy_candidates": redundancy_candidates,
        "governance_actions": governance_actions,
        "priority_actions": priority_actions,
        "remediation_suggestions": remediation_suggestions,
    }


def _is_false_positive_candidate(finding) -> bool:
    if finding.rule_id == "codex.openai_yaml.stale_display_name":
        return True
    if finding.rule_id == "security.binary.opaque_execution":
        return any(finding.path.endswith(suffix) for suffix in (".md", ".mdx", ".txt", ".rst"))
    if finding.rule_id == "security.secret.password_assignment":
        lowered = finding.evidence.lower()
        return any(
            token in lowered
            for token in ("password123", "mypassword", "secret123", "z.string()", "_passwordcontroller")
        )
    return False


def _build_recommendations(
    report: AuditReport,
    summary: dict[str, object],
    false_positive_candidates: list,
    *,
    language: str = "en",
) -> list[str]:
    zh = language == "zh"
    recommendations: list[str] = []
    deterministic_rule_counts = Counter(finding.rule_id for finding in report.deterministic_findings)
    if deterministic_rule_counts:
        top_rule, top_count = deterministic_rule_counts.most_common(1)[0]
        recommendations.append(
            f"优先处理最高频的确定性规则 `{top_rule}`（`{top_count}` 次）。"
            if zh
            else f"Start with the highest-volume deterministic rule: `{top_rule}` (`{top_count}` hits)."
        )
    if summary["redundancy_candidates"]:
        top_candidate = summary["redundancy_candidates"][0]
        recommendations.append(
            f"先复核 `{top_candidate['skill_keys'][0]}` 和 `{top_candidate['skill_keys'][1]}` 这组 `{top_candidate['category']}` 家族重叠。"
            if zh
            else f"Review `{top_candidate['skill_keys'][0]}` and `{top_candidate['skill_keys'][1]}` first for overlap inside `{top_candidate['category']}`."
        )
    trigger_summary = summary["trigger_quality"]
    if trigger_summary["missing_activation_cues"] or trigger_summary["broad_surface_candidates"]:
        recommendations.append(
            "先收紧触发描述，再继续增加相近技能。"
            if zh
            else "Trigger descriptions now have detectable weak spots; tighten ambiguous descriptions before adding more overlapping skills."
        )
    if false_positive_candidates:
        recommendations.append(
            f"先人工复核 `{len(false_positive_candidates)}` 条疑似误报，再按真实错误推进。"
            if zh
            else f"Review `{len(false_positive_candidates)}` likely false-positive findings before treating the global scan as an error-only queue."
        )
    else:
        recommendations.append(
            "当前误报候选较少，剩余 deterministic findings 更接近真实动作项。"
            if zh
            else "False-positive candidates are currently low; remaining deterministic findings look closer to true action items."
        )
    recommendations.append(
        "hook 继续只阻断确定性错误，人工审计继续走前台。"
        if zh
        else "Use hook-run for deterministic block policy and keep exploratory/manual review in foreground audit mode."
    )
    return recommendations


def _translate_category(label: str) -> str:
    mapping = {
        "Document workflows": "文档工作流",
        "Finance and spreadsheet workflows": "财务与表格工作流",
        "Design and frontend": "设计与前端",
        "Mobile development": "移动开发",
        "Developer tooling": "开发工具",
        "Media and multimodal": "媒体与多模态",
        "Web automation and testing": "Web 自动化与测试",
        "General / uncategorized": "通用 / 未归类",
    }
    return mapping.get(label, label)


# ---------------------------------------------------------------------------
# Chinese translation helpers for analysis-layer prose (fixed English strings)
# ---------------------------------------------------------------------------

_GOVERNANCE_TITLES_ZH = {
    "Repair invalid skills before expanding active use": "在扩大使用前先修复无效 skill",
    "Review redundant or family-overlapping skills": "复核重复或同家族 skill 的触发边界",
    "Tighten trigger descriptions with weak activation cues": "收紧触发描述，补充明确激活条件",
    "Review saturated categories for active-set trimming": "复核饱和分类，裁减 active-set",
}

_PRIORITY_WHAT_ZH = {
    "Remove unsafe execution patterns from installed skills":
        "从已安装的 skill 中移除不安全执行模式",
    "Trim redundant family skills before they compete for the same trigger surface":
        "在同家族 skill 产生触发竞争前裁减冗余成员",
    "Rewrite weak trigger descriptions into explicit activation rules":
        "将模糊触发描述改写为明确激活规则",
    "Batch UI metadata polish and oversized SKILL.md cleanup separately from blocking work":
        "将 UI 元数据清理和超长 SKILL.md 拆分单独排期，不与阻断项混排",
}

_PRIORITY_WHY_ZH = {
    "These are real blocking findings that still deserve hard attention even after metadata debt was downgraded.":
        "这些是真实的阻断性发现，即使元数据 debt 已降级，也必须优先处理。",
    "Redundant design-family skills create trigger noise and make active-set curation harder.":
        "同家族冗余 skill 会制造触发噪音，让 active-set 管理越来越难。",
    "Descriptions without clear `use when` cues are hard to route correctly and often cause under-trigger or over-trigger behavior.":
        "没有明确 `use when` 提示的描述难以正确路由，容易导致漏触或乱触发。",
    "These items hurt maintainability and presentation, but they are mostly review-only debt and should not outrank true security or trigger issues.":
        "这些问题影响可维护性和展示质量，但属于 review debt，优先级低于真实安全和触发问题。",
}

_PRIORITY_HOW_ZH = {
    "Inspect each flagged script, replace temp/download execution or pipe-to-shell flows with committed reviewable scripts, then rerun `skill-auditor audit` to confirm the error is gone.":
        "逐一检查被标记的脚本，将 temp/下载目录执行或 pipe-to-shell 流程替换为已提交、可 review 的脚本，再运行 `skill-auditor audit` 确认 error 消失。",
    "Review the pair side-by-side, decide whether one should be canonical, whether one should narrow its trigger wording, or whether both should stay but with explicit family boundaries.":
        "并排对比这对 skill，决定：是否以其中一个为标准版、是否收窄触发描述、或者两者保留但划定明确的家族边界。",
    "For each skill, rewrite the frontmatter description to explicitly state when it should trigger, when it should not trigger, and which neighboring skills it should defer to.":
        "逐一重写 frontmatter description，明确说明：何时触发、何时不触发、与哪些相邻 skill 的边界在哪里。",
    "Split bulky SKILL.md files into references/, and only fix openai.yaml fields for skills that truly need polished Codex UI surfaces.":
        "将过长的 SKILL.md 内容拆分到 references/ 目录；openai.yaml 字段仅在 skill 需要精良 Codex UI 呈现时才修复。",
}

_ACTIVE_REASON_ZH = {
    "category is relatively scarce": "该分类 skill 数量较少",
    "selected despite a saturated category": "从饱和分类中精选",
    "no deterministic warnings": "无确定性警告",
    "no heuristic debt": "无启发式 debt",
    "not currently in a redundant family": "当前不在冗余家族中",
}


def _zh_governance_action(action: dict) -> tuple[str, str]:
    """Return (zh_title, zh_details) for a governance action."""
    title = _GOVERNANCE_TITLES_ZH.get(action["title"], action["title"])
    details = _zh_governance_details(action)
    return title, details


def _zh_governance_details(action: dict) -> str:
    import re
    raw = action["details"]
    # "N skills are invalid under deterministic checks."
    m = re.match(r"(\d+) skills? are? invalid under deterministic checks\.", raw)
    if m:
        return f"{m.group(1)} 个 skill 在确定性检查中判为无效。"
    # "N descriptions lack clear 'use when' style activation cues."
    m = re.match(r"(\d+) descriptions? lack clear 'use when' style activation cues\.", raw)
    if m:
        return f"{m.group(1)} 个 skill 描述缺少明确的激活条件（'use when' 风格）。"
    # "Category X currently contains N skills."
    m = re.match(r"Category (\S+) currently contains (\d+) skills\.", raw)
    if m:
        return f"分类 {m.group(1)} 当前共有 {m.group(2)} 个 skill，已趋于饱和。"
    # Redundancy details: "Shared category X with lexical similarity Y; ..."
    if raw.startswith("Shared category"):
        return _zh_redundancy_reason(raw)
    return raw


def _zh_redundancy_reason(reason: str) -> str:
    import re
    # "Shared category X with lexical similarity Y; shared anchors: A, B. review for redundancy or trigger conflict."
    m = re.match(
        r"Shared category (\S+) with lexical similarity ([\d.]+);(.*?)review for redundancy or trigger conflict\.",
        reason,
        re.DOTALL,
    )
    if not m:
        return reason
    category, similarity, anchors_part = m.group(1), m.group(2), m.group(3).strip()
    anchor_str = ""
    am = re.search(r"shared anchors?: (.+)\.", anchors_part)
    if am:
        anchor_str = f"，共享锚词：{am.group(1)}"
    return f"同属 {category} 分类，词汇相似度 {similarity}{anchor_str}。请复核是否存在冗余或触发冲突。"


def _zh_active_reason(reason: str) -> str:
    """Translate a single active-set reason string."""
    if reason.startswith("covers "):
        label = reason[len("covers "):]
        return f"覆盖{_translate_category(label)}"
    return _ACTIVE_REASON_ZH.get(reason, reason)


def _remediation_why(status: str, language: str) -> str:
    if language == "zh":
        return "当前已被判为无效，需要先修复" if status == "invalid" else "当前不是硬阻断，但已经形成 review debt"
    return (
        "This skill is currently invalid and should be repaired before wider use"
        if status == "invalid"
        else "This is review debt rather than a hard blocker, but it is now concrete enough to queue"
    )
