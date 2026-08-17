"""master markdown 档案 → Candidate 解析器。

格式约定见 docs/master-format.md：
- `## Section` 划分六个已知 section（支持中英文别名）；
- Basic Info 为 `Key: value` 行；
- Education/Experience/Projects 内 `### 名称` 开条目，元数据 `Key: value` 行 + `- ` bullet 列表；
- Skills 为 `- 类别: 逗号分隔技能` 列表；
- bullet 与 Summary 支持多行续行（续行不以 `- `/`Key:`/`#` 开头）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import (
    BasicInfo,
    Bullet,
    Candidate,
    EducationEntry,
    ExperienceEntry,
    ProjectEntry,
    SkillCategory,
    slugify,
)

SECTION_ALIASES: dict[str, str] = {
    "basic info": "basic",
    "basics": "basic",
    "基础信息": "basic",
    "个人信息": "basic",
    "education": "education",
    "教育": "education",
    "教育经历": "education",
    "experience": "experience",
    "work experience": "experience",
    "实习": "experience",
    "经历": "experience",
    "工作经历": "experience",
    "实习经历": "experience",
    "projects": "projects",
    "项目": "projects",
    "项目经历": "projects",
    "skills": "skills",
    "technical skills": "skills",
    "技能": "skills",
    "additional": "additional",
    "其他": "additional",
    "附加": "additional",
}

SECTION_ID_PREFIX = {"education": "edu", "experience": "exp", "projects": "proj", "skills": "skill"}

# `Key: value` 元数据行。key 限制为字母/空格/斜杠，避免误吞 bullet 正文里的冒号。
_KV_RE = re.compile(r"^([A-Za-z][A-Za-z /]*?):\s*(.*)$")
# Skills 行：`- 类别: 技能列表`，类别放宽到任意非冒号字符（含中文）。
_SKILL_RE = re.compile(r"^-\s+([^:：]+)[:：]\s*(.+)$")

_BASIC_FIELDS = {"name", "location", "email", "phone", "summary"}
_EDU_FIELDS = {"degree", "location", "dates", "coursework", "notes"}
_EXP_FIELDS = {"title", "location", "dates"}
_PROJ_FIELDS = {"tagline", "stack"}


@dataclass
class _RawEntry:
    title: str
    meta: list[tuple[str, str]] = field(default_factory=list)  # (key小写, value)
    bullets: list[str] = field(default_factory=list)


class ParseError(ValueError):
    pass


def parse_master(text: str, candidate_id: str | None = None) -> tuple[Candidate, list[str]]:
    """解析 master 档案。返回 (Candidate, 警告列表)。"""
    warnings: list[str] = []
    sections = _split_sections(text, warnings)

    basic = _parse_basic(sections.get("basic", []), warnings)
    if not basic.name:
        raise ParseError("Basic Info 缺少 Name 字段（`Name: 姓名`）")

    used_ids: set[str] = set()
    education = [
        _to_education(raw, _entry_id("education", raw.title, used_ids), warnings)
        for raw in _parse_entries(sections.get("education", []), "education", warnings)
    ]
    experience = [
        _to_experience(raw, _entry_id("experience", raw.title, used_ids), warnings)
        for raw in _parse_entries(sections.get("experience", []), "experience", warnings)
    ]
    projects = [
        _to_project(raw, _entry_id("projects", raw.title, used_ids), warnings)
        for raw in _parse_entries(sections.get("projects", []), "projects", warnings)
    ]
    skills = _parse_skills(sections.get("skills", []), used_ids, warnings)

    candidate = Candidate(
        id=candidate_id or slugify(basic.name),
        basic=basic,
        education=education,
        experience=experience,
        projects=projects,
        skills=skills,
    )
    return candidate, warnings


def _split_sections(text: str, warnings: list[str]) -> dict[str, list[str]]:
    """按 `## ` 切分，返回 {规范section名: 行列表}。HTML 注释行全局剔除。"""
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    in_comment = False
    for line in text.splitlines():
        stripped = line.strip()
        if in_comment:
            if "-->" in stripped:
                in_comment = False
            continue
        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                in_comment = True
            continue
        if stripped.startswith("## ") and not stripped.startswith("###"):
            name = stripped[3:].strip().lower()
            canonical = SECTION_ALIASES.get(name)
            if canonical is None:
                warnings.append(f"跳过未知 section：## {stripped[3:].strip()}")
                current = None
            else:
                current = sections.setdefault(canonical, [])
            continue
        if current is not None:
            current.append(line)
    return sections


def _parse_basic(lines: list[str], warnings: list[str]) -> BasicInfo:
    fields: dict[str, str] = {}
    links: dict[str, str] = {}
    last_key: str | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            last_key = None
            continue
        m = _KV_RE.match(stripped)
        if m:
            key, value = m.group(1).strip(), m.group(2).strip()
            if value.lower().startswith("http"):
                links[key] = value
                last_key = None
            else:
                key_lc = key.lower()
                if key_lc not in _BASIC_FIELDS:
                    warnings.append(f"Basic Info 未知字段被忽略：{key}")
                    last_key = None
                else:
                    fields[key_lc] = value
                    last_key = key_lc
            continue
        if last_key == "summary":  # Summary 支持多行续行
            fields["summary"] = f"{fields['summary']} {stripped}".strip()
        else:
            warnings.append(f"Basic Info 无法识别的行被忽略：{stripped}")
    return BasicInfo(
        name=fields.get("name", ""),
        location=fields.get("location"),
        email=fields.get("email"),
        phone=fields.get("phone"),
        links=links,
        summary=fields.get("summary"),
    )


def _parse_entries(lines: list[str], section: str, warnings: list[str]) -> list[_RawEntry]:
    entries: list[_RawEntry] = []
    current: _RawEntry | None = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            current = _RawEntry(title=stripped[4:].strip())
            entries.append(current)
            continue
        if not stripped:
            continue
        if current is None:
            warnings.append(f"{section} section 中条目外的行被忽略：{stripped}")
            continue
        if stripped.startswith("- "):
            current.bullets.append(stripped[2:].strip())
            continue
        m = _KV_RE.match(stripped) if not current.bullets else None
        if m:
            current.meta.append((m.group(1).strip().lower(), m.group(2).strip()))
        elif current.bullets:  # bullet 续行
            current.bullets[-1] = f"{current.bullets[-1]} {stripped}"
        else:
            warnings.append(f"条目「{current.title}」中无法识别的行被忽略：{stripped}")
    return entries


def _entry_id(section: str, title: str, used: set[str]) -> str:
    base = f"{SECTION_ID_PREFIX[section]}-{slugify(title)}"
    entry_id, n = base, 2
    while entry_id in used:
        entry_id = f"{base}-{n}"
        n += 1
    used.add(entry_id)
    return entry_id


def _bullets(raw: _RawEntry, entry_id: str) -> list[Bullet]:
    return [Bullet(id=f"{entry_id}-b{i}", text=t) for i, t in enumerate(raw.bullets, 1)]


def _meta_dict(raw: _RawEntry, known: set[str], section: str, warnings: list[str]) -> dict[str, str]:
    meta: dict[str, str] = {}
    for key, value in raw.meta:
        if key in known:
            meta[key] = value
        elif key not in ("link", "links"):
            warnings.append(f"{section} 条目「{raw.title}」未知字段被忽略：{key}")
    return meta


def _to_education(raw: _RawEntry, entry_id: str, warnings: list[str]) -> EducationEntry:
    if raw.bullets:
        warnings.append(f"Education 条目「{raw.title}」的 bullet 被忽略（教育条目不支持 bullet）")
    meta = _meta_dict(raw, _EDU_FIELDS, "Education", warnings)
    return EducationEntry(id=entry_id, school=raw.title, **meta)


def _to_experience(raw: _RawEntry, entry_id: str, warnings: list[str]) -> ExperienceEntry:
    meta = _meta_dict(raw, _EXP_FIELDS, "Experience", warnings)
    return ExperienceEntry(id=entry_id, company=raw.title, bullets=_bullets(raw, entry_id), **meta)


def _to_project(raw: _RawEntry, entry_id: str, warnings: list[str]) -> ProjectEntry:
    meta = _meta_dict(raw, _PROJ_FIELDS, "Projects", warnings)
    links = [v for k, v in raw.meta if k == "link"]
    for k, v in raw.meta:
        if k == "links":
            links.extend(part.strip() for part in v.split(",") if part.strip())
    return ProjectEntry(
        id=entry_id, name=raw.title, links=links, bullets=_bullets(raw, entry_id), **meta
    )


def _parse_skills(lines: list[str], used: set[str], warnings: list[str]) -> list[SkillCategory]:
    skills: list[SkillCategory] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        m = _SKILL_RE.match(stripped)
        if not m:
            warnings.append(f"Skills 无法识别的行被忽略（应为 `- 类别: 技能, 技能`）：{stripped}")
            continue
        name = m.group(1).strip()
        skills.append(
            SkillCategory(id=_entry_id("skills", name, used), name=name, items=m.group(2).strip())
        )
    return skills
