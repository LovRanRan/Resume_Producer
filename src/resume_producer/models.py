"""Candidate 数据模型。

每个条目（教育/经历/项目/技能类别）带稳定 ID：section 前缀 + 名称 slug，
如 `proj-wayfinder`、`exp-hirebeat-inc`。bullet ID 为 `<条目ID>-b1`、`-b2`……
AI 定制输出按这些 ID 引用条目，程序端据此做防幻觉校验。
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field


def slugify(text: str) -> str:
    """标题 → 稳定 ID slug（小写，非字母数字折叠为 '-'）。"""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "item"


class Bullet(BaseModel):
    id: str
    text: str


class BasicInfo(BaseModel):
    name: str
    location: str | None = None
    email: str | None = None
    phone: str | None = None
    links: dict[str, str] = Field(default_factory=dict)  # 标签 -> URL，保序
    summary: str | None = None


class EducationEntry(BaseModel):
    id: str
    school: str
    degree: str | None = None
    location: str | None = None
    dates: str | None = None
    coursework: str | None = None
    notes: str | None = None


class ExperienceEntry(BaseModel):
    id: str
    company: str
    title: str | None = None
    location: str | None = None
    dates: str | None = None
    bullets: list[Bullet] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    id: str
    name: str
    tagline: str | None = None
    stack: str | None = None
    links: list[str] = Field(default_factory=list)
    bullets: list[Bullet] = Field(default_factory=list)


class SkillCategory(BaseModel):
    id: str
    name: str
    items: str  # 逗号分隔原文，渲染时原样输出


Entry = EducationEntry | ExperienceEntry | ProjectEntry | SkillCategory


class Candidate(BaseModel):
    id: str
    basic: BasicInfo
    education: list[EducationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    skills: list[SkillCategory] = Field(default_factory=list)

    def entry_index(self) -> dict[str, Entry]:
        """条目 ID → 条目，供 AI 输出校验用。"""
        entries: list[Entry] = [*self.education, *self.experience, *self.projects, *self.skills]
        return {e.id: e for e in entries}

    def bullet_index(self) -> dict[str, Bullet]:
        """bullet ID → Bullet，供防幻觉校验用。"""
        index: dict[str, Bullet] = {}
        for entry in [*self.experience, *self.projects]:
            for bullet in entry.bullets:
                index[bullet.id] = bullet
        return index
