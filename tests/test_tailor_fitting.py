"""tailored candidate 构建 + 单页裁剪循环测试（不调 LLM，不编译 LaTeX）。"""

from pathlib import Path

import pytest

from resume_producer.fitting import FitResult, fit_to_one_page
from resume_producer.parser import parse_master
from resume_producer.renderer import RenderResult
from resume_producer.schemas import SelectedBullet, SelectedEntry, SkillLine, TailoredSelection
from resume_producer.tailor import build_tailored_candidate

EXAMPLE = Path(__file__).parent.parent / "examples" / "candidate_example.md"


@pytest.fixture()
def candidate():
    c, _ = parse_master(EXAMPLE.read_text(encoding="utf-8"))
    return c


@pytest.fixture()
def selection():
    return TailoredSelection(
        projects=[
            SelectedEntry(
                entry_id="proj-coursemap",
                bullets=[SelectedBullet(bullet_id="proj-coursemap-b1", priority=4)],
            ),
            SelectedEntry(
                entry_id="proj-queuectl",
                bullets=[SelectedBullet(bullet_id="proj-queuectl-b1", priority=3)],
            ),
        ],
        experience=[
            SelectedEntry(
                entry_id="exp-nimbus-analytics",
                bullets=[
                    SelectedBullet(bullet_id="exp-nimbus-analytics-b1", priority=1),
                    SelectedBullet(bullet_id="exp-nimbus-analytics-b2", priority=2),
                ],
            ),
        ],
        skills=[SkillLine(category_id="skill-languages", items=["Go", "Python"])],
        rationale="r",
    )


def test_build_tailored_candidate(candidate, selection):
    texts = {"proj-queuectl-b1": "REWRITTEN"}
    tailored, priorities = build_tailored_candidate(candidate, selection, texts, "NEW SUMMARY")

    assert tailored.basic.summary == "NEW SUMMARY"
    # 顺序按 selection，coursemap 在前
    assert [p.id for p in tailored.projects] == ["proj-coursemap", "proj-queuectl"]
    # 改写文本替换、未改写的用原文
    assert tailored.projects[1].bullets[0].text == "REWRITTEN"
    assert "prerequisite graph" in tailored.projects[0].bullets[0].text
    # 未选中的经历条目不出现
    assert [x.id for x in tailored.experience] == ["exp-nimbus-analytics"]
    # 教育全保留、skills 子集重排
    assert len(tailored.education) == 1
    assert tailored.skills[0].items == "Go, Python"
    assert priorities == {
        "proj-coursemap-b1": 4,
        "proj-queuectl-b1": 3,
        "exp-nimbus-analytics-b1": 1,
        "exp-nimbus-analytics-b2": 2,
    }


def _fake_renderer(pages_when_over: int):
    """总 bullet 数 > 阈值 时 2 页，否则 1 页。"""

    def render(cand, output_pdf) -> RenderResult:
        total = sum(len(e.bullets) for e in [*cand.projects, *cand.experience])
        return RenderResult(pdf_path=output_pdf, pages=2 if total > pages_when_over else 1)

    return render


def test_fit_no_trim_needed(candidate, selection):
    tailored, priorities = build_tailored_candidate(candidate, selection, {}, "s")
    fit = fit_to_one_page(tailored, priorities, Path("x.pdf"), render=_fake_renderer(10))
    assert fit.pages == 1
    assert fit.trimmed == []


def test_fit_trims_highest_priority_bullet_first(candidate, selection):
    tailored, priorities = build_tailored_candidate(candidate, selection, {}, "s")
    # 阈值 3：4 条 bullet 需裁 1 条。多 bullet 条目只有 exp（b1=1, b2=2）→ 裁 b2
    fit = fit_to_one_page(tailored, priorities, Path("x.pdf"), render=_fake_renderer(3))
    assert fit.pages == 1
    assert len(fit.trimmed) == 1
    assert "exp-nimbus-analytics-b2" in fit.trimmed[0]
    exp = fit.candidate.experience[0]
    assert [b.id for b in exp.bullets] == ["exp-nimbus-analytics-b1"]


def test_fit_drops_whole_entry_when_bullets_exhausted(candidate, selection):
    tailored, priorities = build_tailored_candidate(candidate, selection, {}, "s")
    # 阈值 2：需从 4 裁到 2。先裁 exp-b2（唯一多 bullet 条目），
    # 之后全部条目只剩 1 bullet → 裁整条目：projects 中 min-priority 最大的是 coursemap(4)
    fit = fit_to_one_page(tailored, priorities, Path("x.pdf"), render=_fake_renderer(2))
    assert fit.pages == 1
    assert [p.id for p in fit.candidate.projects] == ["proj-queuectl"]
    assert len(fit.trimmed) == 2


def test_fit_gives_up_when_nothing_left(candidate, selection):
    tailored, priorities = build_tailored_candidate(candidate, selection, {}, "s")
    fit = fit_to_one_page(tailored, priorities, Path("x.pdf"), render=_fake_renderer(0))
    # 裁到每 section 各剩 1 条目 1 bullet 后放弃，仍 2 页
    assert isinstance(fit, FitResult)
    assert fit.pages == 2
    assert len(fit.candidate.projects) == 1
    assert len(fit.candidate.experience) == 1
