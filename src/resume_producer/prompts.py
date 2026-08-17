"""三次 LLM 调用的 prompt 构建。"""

from __future__ import annotations

from .models import Candidate
from .schemas import JDAnalysis
from .validation import FailedRewrite

SYSTEM = (
    "You are the tailoring engine inside a resume-generation pipeline. "
    "You never invent facts: every claim must come from the candidate archive you are given. "
    "Resume-facing text is written in English; rationale/reason fields are written in Chinese "
    "(they go into a review report for the candidate). "
    "Follow the task instructions and output the requested structure exactly."
)


def analyze_prompt(jd_text: str) -> str:
    return (
        "分析下面这份 Job Description，提取结构化信息：\n"
        "- must_haves：硬性要求（学历/年限/必备技术）\n"
        "- nice_to_haves：加分项\n"
        "- keywords：ATS 关键词（具体技术名词、框架、方法论、领域词；10-25 个，按重要性排序）\n"
        "- seniority：资历定位（如 new grad / junior / mid / senior）\n"
        "- domain：业务领域（如 fintech / devtools / e-commerce，看不出则为 null）\n\n"
        f"<job_description>\n{jd_text}\n</job_description>"
    )


def archive_text(candidate: Candidate) -> str:
    """档案渲染为带 ID 的纯文本，供 LLM#2 阅读。"""
    lines: list[str] = []
    if candidate.basic.summary:
        lines += ["## Summary", candidate.basic.summary, ""]
    lines.append("## Experience")
    for x in candidate.experience:
        lines.append(f"[{x.id}] {x.company} — {x.title or ''} ({x.dates or ''})")
        lines += [f"  [{b.id}] {b.text}" for b in x.bullets]
        lines.append("")
    lines.append("## Projects")
    for p in candidate.projects:
        lines.append(f"[{p.id}] {p.name} — {p.tagline or ''}")
        if p.stack:
            lines.append(f"  Stack: {p.stack}")
        lines += [f"  [{b.id}] {b.text}" for b in p.bullets]
        lines.append("")
    lines.append("## Skills")
    lines += [f"[{s.id}] {s.name}: {s.items}" for s in candidate.skills]
    return "\n".join(lines)


def select_prompt(candidate: Candidate, analysis: JDAnalysis) -> str:
    return (
        "根据 JD 分析结果，从候选人档案中挑选最相关的内容组成一页简历。只做取舍和排序，"
        "不要改写任何文本——只输出 ID。\n\n"
        "规则：\n"
        "- 版面预算（重要）：单页大约只容纳 9-11 条 bullet、5-6 个条目。全部选中的 bullet "
        "总数控制在 9-11 条；宁可少选一个边缘相关的项目，也不要摊薄到每个条目只剩 1 条——"
        "最核心的条目应保有 2 条有分量的 bullet\n"
        "- projects：选 3-4 个最贴合 JD 的项目（第 4 个若只是边缘相关就不选），按相关性排序；"
        "核心项目 2 条 bullet，其余 1 条\n"
        "- experience：实习条目一般全部保留（按时间倒序），最相关的一段 2-3 条 bullet，其余 1-2 条\n"
        "- 每个 bullet 给 priority（整数，全局比较，越大代表越不重要、超页时越先被裁；"
        "被选中的内容中最不相关的给最大值）\n"
        "- skills：每个类别输出与 JD 相关的子集（只能用档案里列出的原词），按相关性重排；"
        "整个类别都不相关可以不输出该类别\n"
        "- rationale：中文，说明选了哪些/没选哪些/为什么（对着 JD 的要求讲）\n\n"
        f"<jd_analysis>\n{analysis.model_dump_json(indent=2)}\n</jd_analysis>\n\n"
        f"<candidate_archive>\n{archive_text(candidate)}\n</candidate_archive>"
    )


def rewrite_prompt(
    selected_bullets: list[tuple[str, str]], summary: str, analysis: JDAnalysis
) -> str:
    bullets_text = "\n".join(f"[{bid}] {text}" for bid, text in selected_bullets)
    return (
        "逐条改写下列已选中的简历 bullet，使其更贴合 JD——同时为每条给出改写理由。\n\n"
        "改写规则（严格遵守）：\n"
        "- 只能使用该 bullet 原文中已有的事实；JD 的关键词只用于调整措辞和强调点，"
        "绝不能引入原文没有的技术、数字或成果\n"
        "- 原文中的数字必须原样保留（不得增删改任何数字）\n"
        "- 用 JD 的语言重新组织：把与 must_haves/keywords 对应的部分前置、强化动词，"
        "弱化或删去与 JD 无关的细节\n"
        "- 保持一条一句、简洁有力；长度不超过原文\n"
        "- 如果原文已经很贴合，可以原样保留（text 与原文相同），reason 说明为什么不改\n"
        "- reason 用中文：说明这条贴合了 JD 的哪些点、强调点怎么调整的\n\n"
        "另外把 summary 也按 JD 改写（同样只能用档案事实，附中文理由）。\n\n"
        f"<jd_analysis>\n{analysis.model_dump_json(indent=2)}\n</jd_analysis>\n\n"
        f"<original_summary>\n{summary}\n</original_summary>\n\n"
        f"<selected_bullets>\n{bullets_text}\n</selected_bullets>"
    )


def repair_prompt(failures: list[FailedRewrite], analysis: JDAnalysis) -> str:
    items = "\n\n".join(
        f"[{f.bullet.source_bullet_id}]\n"
        f"原文: {f.source_text}\n"
        f"你的改写: {f.bullet.text}\n"
        f"校验错误: {f.error}"
        for f in failures
    )
    return (
        "你之前的部分改写未通过程序校验，请修复。规则同前：只能用原文事实，"
        "原文数字必须原样保留、不得引入新数字。修复后仍需贴合 JD、附中文 reason。\n\n"
        f"<jd_analysis>\n{analysis.model_dump_json(indent=2)}\n</jd_analysis>\n\n"
        f"<failed_rewrites>\n{items}\n</failed_rewrites>"
    )
