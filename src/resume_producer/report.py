"""产出报告 report.md 生成。"""

from __future__ import annotations

from .fitting import FitResult
from .models import Candidate
from .tailor import TailorOutcome


def resume_plain_text(candidate: Candidate) -> str:
    """定制简历的纯文本（关键词覆盖检查用）。"""
    parts = [candidate.basic.summary or ""]
    for entry in [*candidate.experience, *candidate.projects]:
        parts += [b.text for b in entry.bullets]
    for proj in candidate.projects:
        parts += [proj.tagline or "", proj.stack or ""]
    parts += [s.items for s in candidate.skills]
    return "\n".join(parts)


def keyword_coverage(keywords: list[str], candidate: Candidate) -> tuple[list[str], list[str]]:
    text = resume_plain_text(candidate).lower()
    covered = [k for k in keywords if k.lower() in text]
    missing = [k for k in keywords if k.lower() not in text]
    return covered, missing


def build_report(outcome: TailorOutcome, fit: FitResult, jd_source: str) -> str:
    a = outcome.analysis
    lines: list[str] = []
    add = lines.append

    add(f"# Tailor 报告 — {a.role_title}" + (f" @ {a.company}" if a.company else ""))
    add("")
    add(f"JD 来源：{jd_source}")
    add("")

    add("## JD 分析")
    add(f"- 资历定位：{a.seniority}" + (f" · 领域：{a.domain}" if a.domain else ""))
    add(f"- 硬性要求：{'；'.join(a.must_haves) or '—'}")
    add(f"- 加分项：{'；'.join(a.nice_to_haves) or '—'}")
    add("")

    add("## 选择理由")
    add(outcome.selection.rationale)
    add("")

    add("## Summary 改写")
    add(f"> {outcome.summary_final}")
    add("")
    add(f"理由：{outcome.summary_reason}")
    add("")

    add("## 逐条改写对照")
    for item in outcome.applied:
        add(f"### `{item.bullet_id}`" + ("　⚠️ 回退原文" if item.fallback else ""))
        add(f"- **原文**：{item.original}")
        if not item.fallback:
            add(f"- **改写**：{item.final}")
        add(f"- **理由**：{item.reason}")
        add("")

    covered, missing = keyword_coverage(a.keywords, fit.candidate)
    add("## 关键词覆盖")
    add(f"- 覆盖 {len(covered)}/{len(a.keywords)}：{', '.join(covered) or '—'}")
    add(f"- 未覆盖：{', '.join(missing) or '—'}")
    if missing:
        add("- 提示：未覆盖项若你确有相关经验，考虑补充进 master 档案。")
    add("")

    if fit.trimmed:
        add("## 单页裁剪记录")
        lines += [f"- {t}" for t in fit.trimmed]
        add(f"- 最终 {fit.pages} 页")
        add("")

    if outcome.validation.issues:
        add("## 校验警告")
        lines += [f"- {i}" for i in outcome.validation.issues]
        add("")

    u = outcome.usage
    add("## 用量")
    add(
        f"- {u.calls} 次 LLM 调用 · 输入 {u.input_tokens:,} / 输出 {u.output_tokens:,} tokens"
        f" · 约 ${u.cost_usd:.3f}"
    )
    add("")
    return "\n".join(lines)
