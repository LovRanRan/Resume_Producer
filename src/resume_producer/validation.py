"""防幻觉校验器（纯函数，不调 LLM）。

三层校验：ID 存在性、数字守恒、技能子集。详见 docs/agent-design.md §2。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import Candidate
from .schemas import RewriteResult, RewrittenBullet, SelectedEntry, SkillLine, TailoredSelection

# 数字 token：先去掉千分位逗号再提取，"2.9K"→"2.9"、"95%"→"95"、"12x"→"12"
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def extract_numbers(text: str) -> set[str]:
    return set(_NUM_RE.findall(re.sub(r"(?<=\d),(?=\d)", "", text)))


def missing_numbers(rewritten: str, source: str) -> set[str]:
    """改写文本中出现、但源文本中不存在的数字。空集 = 通过。"""
    return extract_numbers(rewritten) - extract_numbers(source)


def full_archive_text(candidate: Candidate) -> str:
    """档案全文（summary 数字守恒的比对源）。"""
    parts: list[str] = [candidate.basic.summary or ""]
    for edu in candidate.education:
        parts += [edu.degree or "", edu.dates or "", edu.coursework or "", edu.notes or ""]
    for entry in [*candidate.experience, *candidate.projects]:
        parts += [b.text for b in entry.bullets]
    for proj in candidate.projects:
        parts += [proj.tagline or "", proj.stack or ""]
    for skill in candidate.skills:
        parts.append(skill.items)
    return "\n".join(parts)


@dataclass
class ValidationReport:
    """校验过程中丢弃/修正的记录，全部进产出报告。"""

    issues: list[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        self.issues.append(message)


def validate_selection(
    selection: TailoredSelection, candidate: Candidate, report: ValidationReport
) -> TailoredSelection:
    """ID 存在性 + 技能子集校验，返回清洗后的 selection。"""
    proj_ids = {p.id for p in candidate.projects}
    exp_ids = {x.id for x in candidate.experience}
    bullet_index = candidate.bullet_index()

    def clean_entries(entries: list[SelectedEntry], valid_ids: set[str], kind: str):
        cleaned = []
        for entry in entries:
            if entry.entry_id not in valid_ids:
                report.add(f"丢弃无效{kind}条目引用：{entry.entry_id}")
                continue
            bullets = []
            for b in entry.bullets:
                bullet = bullet_index.get(b.bullet_id)
                if bullet is None or not b.bullet_id.startswith(entry.entry_id + "-b"):
                    report.add(f"丢弃无效 bullet 引用：{b.bullet_id}（条目 {entry.entry_id}）")
                    continue
                bullets.append(b)
            if not bullets:
                report.add(f"条目 {entry.entry_id} 无有效 bullet，整条丢弃")
                continue
            cleaned.append(SelectedEntry(entry_id=entry.entry_id, bullets=bullets))
        return cleaned

    skills = []
    skill_map = {s.id: s for s in candidate.skills}
    for line in selection.skills:
        category = skill_map.get(line.category_id)
        if category is None:
            report.add(f"丢弃无效技能类别引用：{line.category_id}")
            continue
        # 归一化比对，输出时恢复档案原文大小写
        originals = {_norm(item): item.strip() for item in category.items.split(",")}
        kept = []
        for item in line.items:
            original = originals.get(_norm(item))
            if original is None:
                report.add(f"丢弃档案中不存在的技能：{item}（类别 {line.category_id}）")
            else:
                kept.append(original)
        if kept:
            skills.append(SkillLine(category_id=line.category_id, items=kept))

    return TailoredSelection(
        projects=clean_entries(selection.projects, proj_ids, "项目"),
        experience=clean_entries(selection.experience, exp_ids, "经历"),
        skills=skills,
        rationale=selection.rationale,
    )


def _norm(item: str) -> str:
    return re.sub(r"\s+", " ", item.strip().lower())


@dataclass
class FailedRewrite:
    bullet: RewrittenBullet
    source_text: str
    error: str


def validate_rewrites(
    rewrite: RewriteResult,
    candidate: Candidate,
    selected_bullet_ids: set[str],
    report: ValidationReport,
) -> tuple[dict[str, RewrittenBullet], list[FailedRewrite]]:
    """数字守恒校验。返回 (通过的 {bullet_id: RewrittenBullet}, 失败列表供修复)。"""
    bullet_index = candidate.bullet_index()
    valid: dict[str, RewrittenBullet] = {}
    failed: list[FailedRewrite] = []
    for rb in rewrite.bullets:
        source = bullet_index.get(rb.source_bullet_id)
        if source is None or rb.source_bullet_id not in selected_bullet_ids:
            report.add(f"丢弃未选中/不存在的改写目标：{rb.source_bullet_id}")
            continue
        missing = missing_numbers(rb.text, source.text)
        if missing:
            failed.append(
                FailedRewrite(
                    bullet=rb,
                    source_text=source.text,
                    error=f"数字 {', '.join(sorted(missing))} 不在源 bullet 文本中",
                )
            )
        else:
            valid[rb.source_bullet_id] = rb
    return valid, failed


def validate_summary(summary: str, candidate: Candidate) -> set[str]:
    """summary 数字守恒（比对源为档案全文）。返回缺失数字，空集 = 通过。"""
    return missing_numbers(summary, full_archive_text(candidate))
