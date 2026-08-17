"""tailor pipeline 编排：JD 分析 → 选择 → 改写 → 校验/修复 → 构建定制 Candidate。

渲染与单页裁剪在 fitting.py，产出落盘在 cli.py。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .llm import UsageTracker, parse_structured
from .models import Bullet, Candidate, ExperienceEntry, ProjectEntry, SkillCategory
from .prompts import SYSTEM, analyze_prompt, repair_prompt, rewrite_prompt, select_prompt
from .schemas import JDAnalysis, RepairResult, RewriteResult, TailoredSelection
from .validation import (
    ValidationReport,
    validate_rewrites,
    validate_selection,
    validate_summary,
)


@dataclass
class AppliedBullet:
    """一条 bullet 的最终去向（进报告的三栏对照）。"""

    bullet_id: str
    original: str
    final: str
    reason: str
    fallback: bool = False  # True = 回退了原文


@dataclass
class TailorOutcome:
    analysis: JDAnalysis
    selection: TailoredSelection
    rewrite: RewriteResult
    applied: list[AppliedBullet]  # 按简历展示顺序
    summary_final: str
    summary_reason: str
    tailored: Candidate
    priorities: dict[str, int]
    validation: ValidationReport
    usage: UsageTracker


def run_tailor(
    candidate: Candidate, jd_text: str, progress: Callable[[str], None] = lambda _: None
) -> TailorOutcome:
    usage = UsageTracker()
    report = ValidationReport()
    bullet_index = candidate.bullet_index()

    progress("① JD 分析中…")
    analysis = parse_structured(SYSTEM, analyze_prompt(jd_text), JDAnalysis, usage, effort="low")

    progress("② 条目选择中…")
    selection = parse_structured(
        SYSTEM, select_prompt(candidate, analysis), TailoredSelection, usage
    )
    selection = validate_selection(selection, candidate, report)

    selected_pairs = [
        (b.bullet_id, bullet_index[b.bullet_id].text)
        for entry in [*selection.projects, *selection.experience]
        for b in entry.bullets
    ]
    selected_ids = {bid for bid, _ in selected_pairs}

    progress(f"③ 逐条改写中（{len(selected_pairs)} 条 bullet）…")
    rewrite = parse_structured(
        SYSTEM,
        rewrite_prompt(selected_pairs, candidate.basic.summary or "", analysis),
        RewriteResult,
        usage,
    )
    valid, failed = validate_rewrites(rewrite, candidate, selected_ids, report)

    if failed:
        progress(f"④ 校验未过 {len(failed)} 条，LLM 修复中…")
        repair = parse_structured(
            SYSTEM, repair_prompt(failed, analysis), RepairResult, usage
        )
        repaired_result = RewriteResult(summary="", summary_reason="", bullets=repair.bullets)
        still_failed_ids = {f.bullet.source_bullet_id for f in failed}
        revalid, refailed = validate_rewrites(repaired_result, candidate, still_failed_ids, report)
        valid.update(revalid)
        for f in refailed:
            report.add(f"修复后仍未通过，回退原文：{f.bullet.source_bullet_id}（{f.error}）")

    # 逐条落定：通过的用改写，其余回退原文
    applied: list[AppliedBullet] = []
    for bid, original in selected_pairs:
        rb = valid.get(bid)
        if rb is not None:
            applied.append(
                AppliedBullet(bullet_id=bid, original=original, final=rb.text, reason=rb.reason)
            )
        else:
            if bid not in {b.source_bullet_id for b in rewrite.bullets}:
                report.add(f"改写输出缺失该 bullet，保留原文：{bid}")
            applied.append(
                AppliedBullet(
                    bullet_id=bid,
                    original=original,
                    final=original,
                    reason="校验未通过或改写缺失，保留档案原文",
                    fallback=True,
                )
            )

    # summary：数字守恒不过则回退
    summary_final, summary_reason = rewrite.summary, rewrite.summary_reason
    missing = validate_summary(summary_final, candidate)
    if missing or not summary_final.strip():
        report.add(f"summary 校验未过（数字 {', '.join(sorted(missing)) or '空输出'}），回退原文")
        summary_final = candidate.basic.summary or ""
        summary_reason = "校验未通过，保留档案原 summary"

    tailored, priorities = build_tailored_candidate(
        candidate, selection, {a.bullet_id: a.final for a in applied}, summary_final
    )
    return TailorOutcome(
        analysis=analysis,
        selection=selection,
        rewrite=rewrite,
        applied=applied,
        summary_final=summary_final,
        summary_reason=summary_reason,
        tailored=tailored,
        priorities=priorities,
        validation=report,
        usage=usage,
    )


def build_tailored_candidate(
    candidate: Candidate,
    selection: TailoredSelection,
    texts: dict[str, str],
    summary: str,
) -> tuple[Candidate, dict[str, int]]:
    """Selection + 最终文本 → 渲染用 Candidate 子集 + 裁剪优先级表。"""
    entry_index = candidate.entry_index()
    bullet_index = candidate.bullet_index()
    priorities: dict[str, int] = {}

    def rebuild(selected, cls):
        entries = []
        for sel in selected:
            source = entry_index[sel.entry_id]
            bullets = []
            for sb in sel.bullets:
                priorities[sb.bullet_id] = sb.priority
                bullets.append(
                    Bullet(id=sb.bullet_id, text=texts.get(sb.bullet_id, bullet_index[sb.bullet_id].text))
                )
            entries.append(source.model_copy(update={"bullets": bullets}))
        return entries

    basic = candidate.basic.model_copy(update={"summary": summary})
    skills = [
        SkillCategory(
            id=line.category_id,
            name=next(s.name for s in candidate.skills if s.id == line.category_id),
            items=", ".join(line.items),
        )
        for line in selection.skills
    ]
    tailored = Candidate(
        id=candidate.id,
        basic=basic,
        education=[e.model_copy(deep=True) for e in candidate.education],
        experience=rebuild(selection.experience, ExperienceEntry),
        projects=rebuild(selection.projects, ProjectEntry),
        skills=skills,
    )
    return tailored, priorities
