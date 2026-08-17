"""tailor 任务层：pipeline + 渲染裁剪 + 产出落盘，CLI 与 API 共用。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .fitting import FitResult, fit_to_one_page
from .models import Candidate, slugify
from .renderer import render_tex
from .report import build_report, keyword_coverage
from .storage import data_dir
from .tailor import TailorOutcome, run_tailor


@dataclass
class TailorJobResult:
    run_id: str
    out_dir: Path
    outcome: TailorOutcome
    fit: FitResult

    def summary(self) -> dict:
        """API/CLI 展示用的结果摘要（可 JSON 序列化）。"""
        covered, _ = keyword_coverage(self.outcome.analysis.keywords, self.fit.candidate)
        return {
            "run_id": self.run_id,
            "role_title": self.outcome.analysis.role_title,
            "company": self.outcome.analysis.company,
            "pages": self.fit.pages,
            "projects": len(self.fit.candidate.projects),
            "experience": len(self.fit.candidate.experience),
            "bullets": sum(
                len(e.bullets)
                for e in [*self.fit.candidate.projects, *self.fit.candidate.experience]
            ),
            "trimmed": len(self.fit.trimmed),
            "fallbacks": sum(1 for a in self.outcome.applied if a.fallback),
            "keywords_covered": len(covered),
            "keywords_total": len(self.outcome.analysis.keywords),
            "cost_usd": round(self.outcome.usage.cost_usd, 4),
            "llm_calls": self.outcome.usage.calls,
        }


def run_tailor_job(
    candidate: Candidate,
    jd_text: str,
    jd_source: str,
    progress: Callable[[str], None] = lambda _: None,
) -> TailorJobResult:
    """跑完整 tailor 并把全套产出存档到 data/<id>/outputs/<run_id>/。"""
    outcome = run_tailor(candidate, jd_text, progress=progress)

    slug = slugify(outcome.analysis.company or outcome.analysis.role_title)
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{slug}"  # noqa: DTZ005 — 本地时间命名目录
    out_dir = data_dir() / candidate.id / "outputs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "jd.txt").write_text(jd_text, encoding="utf-8")
    (out_dir / "jd_analysis.json").write_text(
        outcome.analysis.model_dump_json(indent=2), encoding="utf-8"
    )
    (out_dir / "selection.json").write_text(
        outcome.selection.model_dump_json(indent=2), encoding="utf-8"
    )
    (out_dir / "rewrite.json").write_text(
        outcome.rewrite.model_dump_json(indent=2), encoding="utf-8"
    )

    progress("⑤ 渲染 + 单页裁剪中…")
    fit = fit_to_one_page(outcome.tailored, outcome.priorities, out_dir / "resume.pdf")
    (out_dir / "resume.tex").write_text(render_tex(fit.candidate), encoding="utf-8")
    (out_dir / "report.md").write_text(build_report(outcome, fit, jd_source), encoding="utf-8")

    return TailorJobResult(run_id=run_id, out_dir=out_dir, outcome=outcome, fit=fit)
