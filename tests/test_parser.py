"""解析器测试：以 examples/candidate_example.md 为主 fixture。"""

from pathlib import Path

import pytest

from resume_producer.models import slugify
from resume_producer.parser import ParseError, parse_master

EXAMPLE = Path(__file__).parent.parent / "examples" / "candidate_example.md"


@pytest.fixture()
def example():
    candidate, warnings = parse_master(EXAMPLE.read_text(encoding="utf-8"))
    return candidate, warnings


def test_example_parses_clean(example):
    _, warnings = example
    assert warnings == []


def test_basic_info(example):
    c, _ = example
    assert c.id == "alex-chen"
    assert c.basic.name == "Alex Chen"
    assert c.basic.email == "alex.chen.example@gmail.com"
    assert c.basic.links["GitHub"] == "https://github.com/alexchen-example"
    assert c.basic.links["Portfolio"] == "https://alexchen.example.dev"  # 任意 http key 收进 links
    assert "observability-first infrastructure" in c.basic.summary  # Summary 多行拼接


def test_sections_and_ids(example):
    c, _ = example
    assert [e.id for e in c.education] == ["edu-university-of-washington"]
    assert [e.id for e in c.experience] == ["exp-nimbus-analytics", "exp-campus-it-services"]
    assert [p.id for p in c.projects] == ["proj-queuectl", "proj-coursemap"]
    assert [s.name for s in c.skills] == ["Languages", "Backend", "Observability"]


def test_entry_fields(example):
    c, _ = example
    edu = c.education[0]
    assert edu.degree == "B.S. in Computer Science"
    assert edu.dates == "Jun 2024"
    exp = c.experience[0]
    assert exp.title == "Software Engineer Intern"
    assert len(exp.bullets) == 2
    proj = c.projects[0]
    assert proj.tagline == "CLI for inspecting and replaying dead-letter queues"
    assert proj.links == ["https://github.com/alexchen-example/queuectl"]


def test_bullet_continuation_and_ids(example):
    c, _ = example
    bullet = c.experience[0].bullets[0]
    assert bullet.id == "exp-nimbus-analytics-b1"
    # 续行被拼接为一条
    assert "cutting end-to-end latency from 15 min to 40 s." in bullet.text


def test_indexes(example):
    c, _ = example
    assert "proj-queuectl" in c.entry_index()
    assert "exp-nimbus-analytics-b2" in c.bullet_index()


def test_missing_name_raises():
    with pytest.raises(ParseError):
        parse_master("## Basic Info\nEmail: a@b.c\n")


def test_explicit_candidate_id():
    c, _ = parse_master("## Basic Info\nName: Foo Bar\n", candidate_id="custom")
    assert c.id == "custom"


def test_unknown_section_warns():
    _, warnings = parse_master("## Basic Info\nName: X\n\n## Hobbies\n- fishing\n")
    assert any("未知 section" in w for w in warnings)


def test_chinese_aliases_and_skill_colon():
    text = (
        "## 基础信息\nName: 张三\n\n"
        "## 实习\n### 公司A\nTitle: 工程师\n\n- 做了一件事。\n\n"
        "## 技能\n- 语言：Python, Go\n"
    )
    c, warnings = parse_master(text)
    assert warnings == []
    assert c.experience[0].id == "exp-a"  # 中文标题 slug 退化为可用 ASCII
    assert c.skills[0].name == "语言"
    assert c.skills[0].items == "Python, Go"


def test_duplicate_titles_get_unique_ids():
    text = (
        "## Basic Info\nName: X\n\n"
        "## Projects\n### demo\n- a\n\n### demo\n- b\n"
    )
    c, _ = parse_master(text)
    assert [p.id for p in c.projects] == ["proj-demo", "proj-demo-2"]


def test_multiple_links():
    text = (
        "## Basic Info\nName: X\n\n"
        "## Projects\n### tools\nLink: https://a.example\nLink: https://b.example\n- x\n"
    )
    c, _ = parse_master(text)
    assert c.projects[0].links == ["https://a.example", "https://b.example"]


def test_slugify():
    assert slugify("HireBeat Inc.") == "hirebeat-inc"
    assert slugify("MCP Codebase Tools") == "mcp-codebase-tools"
    assert slugify("!!!") == "item"
