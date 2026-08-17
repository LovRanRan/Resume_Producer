"""resume CLI：add / list / show。"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .parser import ParseError, parse_master
from .storage import list_candidates, load_candidate, save_candidate

app = typer.Typer(
    help="按 JD 定制简历生成器。master markdown 档案 → 定制简历 PDF。",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


@app.command()
def add(
    file: Annotated[Path, typer.Argument(help="master markdown 档案路径", exists=True)],
    candidate_id: Annotated[
        str | None, typer.Option("--id", help="candidate ID（默认取姓名 slug）")
    ] = None,
) -> None:
    """解析 master 档案并存储为 candidate。"""
    try:
        candidate, warnings = parse_master(file.read_text(encoding="utf-8"), candidate_id)
    except ParseError as e:
        typer.secho(f"解析失败：{e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e
    for w in warnings:
        typer.secho(f"警告：{w}", fg=typer.colors.YELLOW, err=True)
    path = save_candidate(candidate, source_md=file)
    typer.echo(
        f"已存储 candidate '{candidate.id}'（{candidate.basic.name}）→ {path}\n"
        f"  教育 {len(candidate.education)} · 经历 {len(candidate.experience)} · "
        f"项目 {len(candidate.projects)} · 技能类别 {len(candidate.skills)} · "
        f"bullet {len(candidate.bullet_index())}"
    )


@app.command(name="list")
def list_cmd() -> None:
    """列出所有 candidate。"""
    candidates = list_candidates()
    if not candidates:
        typer.echo("还没有 candidate。用 `resume add <master.md>` 导入。")
        return
    for c in candidates:
        typer.echo(
            f"{c.id:<24} {c.basic.name:<20} "
            f"教育{len(c.education)} 经历{len(c.experience)} "
            f"项目{len(c.projects)} bullet{len(c.bullet_index())}"
        )


@app.command()
def show(
    candidate_id: Annotated[str, typer.Argument(help="candidate ID")],
    full: Annotated[bool, typer.Option("--full", help="显示 bullet 全文")] = False,
) -> None:
    """查看 candidate 详情（含条目 ID）。"""
    try:
        c = load_candidate(candidate_id)
    except FileNotFoundError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e

    b = c.basic
    contact = " | ".join(x for x in [b.location, b.email, b.phone] if x)
    typer.echo(f"{b.name}  ({c.id})")
    if contact:
        typer.echo(contact)
    for label, url in b.links.items():
        typer.echo(f"{label}: {url}")
    if b.summary:
        typer.echo(f"\n{b.summary}")

    typer.echo("\n== Education ==")
    for e in c.education:
        typer.echo(f"[{e.id}] {e.school} — {e.degree or ''} · {e.dates or ''}")
        if e.coursework:
            typer.echo(f"    Coursework: {e.coursework}")

    typer.echo("\n== Experience ==")
    for exp in c.experience:
        typer.echo(f"[{exp.id}] {exp.company} — {exp.title or ''} · {exp.dates or ''}")
        _print_bullets(exp.bullets, full)

    typer.echo("\n== Projects ==")
    for p in c.projects:
        typer.echo(f"[{p.id}] {p.name} — {p.tagline or ''}")
        if p.stack:
            typer.echo(f"    Stack: {p.stack}")
        _print_bullets(p.bullets, full)

    typer.echo("\n== Skills ==")
    for s in c.skills:
        typer.echo(f"[{s.id}] {s.name}: {s.items}")


@app.command()
def render(
    candidate_id: Annotated[str, typer.Argument(help="candidate ID")],
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="输出 PDF 路径（默认 output/<id>.pdf）")
    ] = None,
) -> None:
    """完整档案直接渲染 PDF（不经 AI，用于验证模板）。"""
    from .renderer import RenderError, render_pdf

    try:
        candidate = load_candidate(candidate_id)
    except FileNotFoundError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e
    output = output or Path("output") / f"{candidate_id}.pdf"
    try:
        result = render_pdf(candidate, output)
    except RenderError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e
    typer.echo(f"已渲染 {result.pdf_path}（{result.pages} 页）")
    if result.pages > 1:
        typer.secho(
            "提示：完整档案超过 1 页属正常；定制简历（tailor）会做单页控制。",
            fg=typer.colors.YELLOW,
        )


@app.command()
def tailor(
    candidate_id: Annotated[str, typer.Argument(help="candidate ID")],
    jd_file: Annotated[
        Path | None, typer.Option("--jd-file", help="JD 文本文件", exists=True)
    ] = None,
    jd_url: Annotated[str | None, typer.Option("--jd-url", help="JD 页面 URL（尽力抓取）")] = None,
    jd_text: Annotated[str | None, typer.Option("--jd-text", help="JD 文本")] = None,
) -> None:
    """按 JD 生成定制简历 PDF（核心命令）。不带 JD 参数时交互式粘贴。"""
    import sys
    from datetime import datetime

    from .fitting import fit_to_one_page
    from .jd_input import JDInputError, jd_from_file, jd_from_url
    from .llm import LLMError
    from .models import slugify
    from .renderer import RenderError, render_tex
    from .report import build_report
    from .storage import data_dir
    from .tailor import run_tailor

    try:
        candidate = load_candidate(candidate_id)
    except FileNotFoundError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e

    try:
        if jd_file:
            jd, jd_source = jd_from_file(jd_file), str(jd_file)
        elif jd_url:
            jd, jd_source = jd_from_url(jd_url), jd_url
        elif jd_text:
            jd, jd_source = jd_text, "命令行文本"
        else:
            typer.echo("粘贴 JD 文本，结束后按 Ctrl-D：")
            jd, jd_source = sys.stdin.read().strip(), "交互粘贴"
            if not jd:
                typer.secho("JD 为空。", fg=typer.colors.RED, err=True)
                raise typer.Exit(1)
    except JDInputError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e

    try:
        outcome = run_tailor(candidate, jd, progress=typer.echo)
    except LLMError as e:
        typer.secho(f"LLM 调用失败：{e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e

    slug = slugify(outcome.analysis.company or outcome.analysis.role_title)
    out_dir = data_dir() / candidate_id / "outputs" / (
        f"{datetime.now():%Y%m%d-%H%M%S}-{slug}"  # noqa: DTZ005 — 本地时间命名目录
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "jd.txt").write_text(jd, encoding="utf-8")
    (out_dir / "jd_analysis.json").write_text(
        outcome.analysis.model_dump_json(indent=2), encoding="utf-8"
    )
    (out_dir / "selection.json").write_text(
        outcome.selection.model_dump_json(indent=2), encoding="utf-8"
    )
    (out_dir / "rewrite.json").write_text(
        outcome.rewrite.model_dump_json(indent=2), encoding="utf-8"
    )

    typer.echo("⑤ 渲染 + 单页裁剪中…")
    try:
        fit = fit_to_one_page(outcome.tailored, outcome.priorities, out_dir / "resume.pdf")
    except RenderError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e
    (out_dir / "resume.tex").write_text(render_tex(fit.candidate), encoding="utf-8")
    (out_dir / "report.md").write_text(build_report(outcome, fit, jd_source), encoding="utf-8")

    fallbacks = sum(1 for x in outcome.applied if x.fallback)
    typer.echo(
        f"\n完成：{outcome.analysis.role_title}"
        + (f" @ {outcome.analysis.company}" if outcome.analysis.company else "")
    )
    typer.echo(
        f"  项目 {len(fit.candidate.projects)} · 经历 {len(fit.candidate.experience)}"
        f" · bullet {sum(len(e.bullets) for e in [*fit.candidate.projects, *fit.candidate.experience])}"
        f" · {fit.pages} 页"
        + (f" · 裁剪 {len(fit.trimmed)} 次" if fit.trimmed else "")
        + (f" · 回退原文 {fallbacks} 条" if fallbacks else "")
    )
    typer.echo(f"  成本 ${outcome.usage.cost_usd:.3f}（{outcome.usage.calls} 次调用）")
    typer.echo(f"  PDF：{out_dir / 'resume.pdf'}")
    typer.echo(f"  报告：{out_dir / 'report.md'}")
    if fit.pages > 1:
        typer.secho("警告：裁无可裁仍超 1 页，请检查档案条目长度。", fg=typer.colors.YELLOW)


def _print_bullets(bullets: list, full: bool) -> None:
    for bullet in bullets:
        text = bullet.text if full else _truncate(bullet.text, 80)
        typer.echo(f"    [{bullet.id}] {text}")


def _truncate(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


if __name__ == "__main__":
    app()
