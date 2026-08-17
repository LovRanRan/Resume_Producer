"""LLM 结构化输出 schema（三次调用的契约）。

所有字段均为必填（可空字段用 `X | None` 但不给默认值），以兼容 structured outputs
对 required 的要求；schema 保持平坦、无递归、无数值约束。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class JDAnalysis(BaseModel):
    """LLM#1：JD 分析结果。"""

    role_title: str
    company: str | None
    seniority: str = Field(description='资历要求，如 "new grad" / "junior" / "senior"')
    must_haves: list[str] = Field(description="硬性要求")
    nice_to_haves: list[str]
    keywords: list[str] = Field(description="ATS 关键词：技术名词、领域词")
    domain: str | None = Field(description="业务领域信号")


class SelectedBullet(BaseModel):
    bullet_id: str
    priority: int = Field(description="全局裁剪优先级，越大越先被裁")


class SelectedEntry(BaseModel):
    entry_id: str
    bullets: list[SelectedBullet]


class SkillLine(BaseModel):
    category_id: str
    items: list[str] = Field(description="原类别 items 的子集，按 JD 相关性重排")


class TailoredSelection(BaseModel):
    """LLM#2：选择结果（只含 ID 与排序，不含改写文本）。"""

    projects: list[SelectedEntry] = Field(description="按展示顺序")
    experience: list[SelectedEntry]
    skills: list[SkillLine]
    rationale: str = Field(description="整体选择理由（中文，进报告）")


class RewrittenBullet(BaseModel):
    source_bullet_id: str
    text: str = Field(description="改写后的 bullet（英文，可与原文相同）")
    reason: str = Field(description="逐条改写理由（中文）：贴合了 JD 的哪些点、强调如何调整")


class RewriteResult(BaseModel):
    """LLM#3：改写结果（逐条带理由）。"""

    summary: str = Field(description="按 JD 改写的 summary（英文，受事实约束）")
    summary_reason: str = Field(description="summary 改写理由（中文）")
    bullets: list[RewrittenBullet]


class RepairResult(BaseModel):
    """校验失败 bullet 的修复输出。"""

    bullets: list[RewrittenBullet]
