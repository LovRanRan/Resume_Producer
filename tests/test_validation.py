"""防幻觉校验器测试。"""

from pathlib import Path

import pytest

from resume_producer.parser import parse_master
from resume_producer.schemas import (
    RewriteResult,
    RewrittenBullet,
    SelectedBullet,
    SelectedEntry,
    SkillLine,
    TailoredSelection,
)
from resume_producer.validation import (
    ValidationReport,
    extract_numbers,
    missing_numbers,
    validate_rewrites,
    validate_selection,
    validate_summary,
)

EXAMPLE = Path(__file__).parent.parent / "examples" / "candidate_example.md"


@pytest.fixture()
def candidate():
    c, _ = parse_master(EXAMPLE.read_text(encoding="utf-8"))
    return c


def test_extract_numbers():
    assert extract_numbers("~2.9K LOC, 49 jobs (12 qualified), 95%") == {"2.9", "49", "12", "95"}
    assert extract_numbers("1,200 courses") == {"1200"}
    assert extract_numbers("no numbers here") == set()


def test_missing_numbers():
    src = "cut latency from 15 min to 40 s across 2M events/day"
    assert missing_numbers("reduced latency 15min→40s for 2M daily events", src) == set()
    assert missing_numbers("cut latency by 96%", src) == {"96"}


def test_validate_selection_drops_bad_ids(candidate):
    report = ValidationReport()
    sel = TailoredSelection(
        projects=[
            SelectedEntry(
                entry_id="proj-queuectl",
                bullets=[
                    SelectedBullet(bullet_id="proj-queuectl-b1", priority=1),
                    SelectedBullet(bullet_id="proj-queuectl-b99", priority=2),  # 不存在
                    SelectedBullet(bullet_id="proj-coursemap-b1", priority=3),  # 属别的条目
                ],
            ),
            SelectedEntry(  # 条目不存在
                entry_id="proj-fake", bullets=[SelectedBullet(bullet_id="x", priority=1)]
            ),
        ],
        experience=[],
        skills=[],
        rationale="r",
    )
    cleaned = validate_selection(sel, candidate, report)
    assert [e.entry_id for e in cleaned.projects] == ["proj-queuectl"]
    assert [b.bullet_id for b in cleaned.projects[0].bullets] == ["proj-queuectl-b1"]
    assert len(report.issues) == 3


def test_validate_selection_skills_subset(candidate):
    report = ValidationReport()
    sel = TailoredSelection(
        projects=[],
        experience=[],
        skills=[
            SkillLine(category_id="skill-languages", items=["python", "Rust", "Go"]),
            SkillLine(category_id="skill-nope", items=["x"]),
        ],
        rationale="r",
    )
    cleaned = validate_selection(sel, candidate, report)
    # "python" 归一化命中并恢复原文大小写；Rust 不在档案里被丢弃
    assert cleaned.skills[0].items == ["Python", "Go"]
    assert len(cleaned.skills) == 1
    assert any("Rust" in i for i in report.issues)
    assert any("skill-nope" in i for i in report.issues)


def test_validate_rewrites(candidate):
    report = ValidationReport()
    selected = {"exp-nimbus-analytics-b1", "exp-nimbus-analytics-b2"}
    rewrite = RewriteResult(
        summary="s",
        summary_reason="r",
        bullets=[
            RewrittenBullet(
                source_bullet_id="exp-nimbus-analytics-b1",
                text="Built Kafka pipeline handling 2M events/day, cutting latency 15 min → 40 s",
                reason="ok",
            ),
            RewrittenBullet(
                source_bullet_id="exp-nimbus-analytics-b2",
                text="Halved triage time by 50% via OpenTelemetry",  # 50 是编造数字
                reason="bad",
            ),
            RewrittenBullet(source_bullet_id="proj-queuectl-b1", text="t", reason="未选中"),
        ],
    )
    valid, failed = validate_rewrites(rewrite, candidate, selected, report)
    assert set(valid) == {"exp-nimbus-analytics-b1"}
    assert len(failed) == 1
    assert "50" in failed[0].error
    assert any("proj-queuectl-b1" in i for i in report.issues)


def test_validate_summary(candidate):
    assert validate_summary("Backend engineer with Python/Go", candidate) == set()
    assert validate_summary("10 years of experience", candidate) == {"10"}
