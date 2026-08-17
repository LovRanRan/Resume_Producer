"""单页裁剪循环（纯程序，不调 LLM）。

超页时按 LLM#2 给出的 priority 裁 bullet（每条目至少保留 1 条），
bullet 裁无可裁后整条目裁（先项目后经历），重渲直到 1 页。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .models import Candidate
from .renderer import RenderResult, render_pdf

MAX_ITERS = 15


class _Renderer(Protocol):
    def __call__(self, candidate: Candidate, output_pdf: Path) -> RenderResult: ...


@dataclass
class FitResult:
    candidate: Candidate
    pages: int
    trimmed: list[str] = field(default_factory=list)  # 裁剪记录（进报告）


def fit_to_one_page(
    candidate: Candidate,
    priorities: dict[str, int],
    output_pdf: Path,
    render: _Renderer | Callable = render_pdf,
) -> FitResult:
    cand = candidate.model_copy(deep=True)
    trimmed: list[str] = []
    pages = 0
    for _ in range(MAX_ITERS):
        pages = render(cand, output_pdf).pages
        if pages <= 1:
            break
        desc = _trim_one(cand, priorities)
        if desc is None:  # 无可裁，接受超页
            break
        trimmed.append(desc)
    return FitResult(candidate=cand, pages=pages, trimmed=trimmed)


def _trim_one(cand: Candidate, priorities: dict[str, int]) -> str | None:
    """原地裁掉一个单位。优先：多 bullet 条目中 priority 最高的 bullet；否则整条目。"""
    entries = [*cand.projects, *cand.experience]

    # 1) 可裁 bullet：所在条目剩余 bullet > 1
    candidates = [
        (priorities.get(b.id, 0), entry, b)
        for entry in entries
        if len(entry.bullets) > 1
        for b in entry.bullets
    ]
    if candidates:
        _, entry, bullet = max(candidates, key=lambda t: t[0])
        entry.bullets.remove(bullet)
        return f"裁掉 bullet {bullet.id}（priority {priorities.get(bullet.id, 0)}）"

    # 2) 整条目：先项目后经历，裁"最重要 bullet 也最不重要"的条目；至少各留 1 条
    for section_name, section in (("项目", cand.projects), ("经历", cand.experience)):
        if len(section) > 1:
            entry = max(
                section, key=lambda e: min(priorities.get(b.id, 0) for b in e.bullets)
            )
            section.remove(entry)
            return f"裁掉整个{section_name}条目 {entry.id}"
    return None
