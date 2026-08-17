"""PDF 渲染：Candidate → Jinja2 填 LaTeX 模板 → XeLaTeX 编译。

模板分隔符用 \\VAR{} / \\BLOCK{}，避免与 LaTeX 的 {{ }} 冲突。
所有档案文本经 `tex` 过滤器转义；渲染器返回 PDF 页数，供单页控制（Phase 3）使用。
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader

from .models import Candidate

TEMPLATE_DIR = Path(__file__).parent / "templates"
DEFAULT_TEMPLATE = "classic.tex.j2"

_TEX_MAP = {
    "--": r"-{}-",  # 防 TeX 连字成 en-dash（如 `mypy --strict`）
    "/": r"/\allowbreak{}",  # 允许长斜杠串（AWS Lambda/SQS/DynamoDB/ECS）断行
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "→": r"$\rightarrow$",
}
_TEX_RE = re.compile("|".join(re.escape(c) for c in _TEX_MAP))


def escape_tex(value: object) -> str:
    """LaTeX 特殊字符转义（单遍替换，None → 空串）。"""
    if value is None:
        return ""
    return _TEX_RE.sub(lambda m: _TEX_MAP[m.group()], str(value))


class RenderError(RuntimeError):
    pass


@dataclass
class RenderResult:
    pdf_path: Path
    pages: int


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        block_start_string=r"\BLOCK{",
        block_end_string="}",
        variable_start_string=r"\VAR{",
        variable_end_string="}",
        comment_start_string=r"\#{",
        comment_end_string="}",
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
    )
    env.filters["tex"] = escape_tex
    return env


def _link_label(url: str, single: bool) -> str:
    """单链接 → 域名通称（github.com → GitHub）；多链接 → URL 末段区分。"""
    parsed = urlparse(url)
    if single:
        host = (parsed.hostname or url).removeprefix("www.")
        return "GitHub" if host == "github.com" else host
    last = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    return last or (parsed.hostname or url)


def _href(url: str, label: str) -> str:
    return rf"\href{{{url}}}{{{escape_tex(label)}}}"


def _joined(parts: list[str | None], sep: str = " · ") -> str:
    return sep.join(p for p in parts if p)


def build_context(candidate: Candidate) -> dict:
    """Candidate → 模板上下文。*_tex 字段为已构建好的 LaTeX 片段（模板不再转义）。"""
    b = candidate.basic
    contact_parts = [escape_tex(p) for p in [b.location, b.phone] if p]
    if b.email:
        contact_parts.insert(1 if b.location else 0, _href(f"mailto:{b.email}", b.email))
    contact_parts += [_href(url, label) for label, url in b.links.items()]

    education = [
        {
            "school": e.school,
            "location": e.location,
            "degree": e.degree,
            "dates_line": _joined([e.dates, e.notes]),
            "coursework": e.coursework,
        }
        for e in candidate.education
    ]
    experience = [
        {
            "company": x.company,
            "title": x.title,
            "right": _joined([x.location, x.dates]),
            "bullets": x.bullets,
        }
        for x in candidate.experience
    ]
    projects = [
        {
            "name": p.name,
            "tagline": p.tagline,
            "stack": p.stack,
            "links_tex": " · ".join(
                _href(url, _link_label(url, single=len(p.links) == 1)) for url in p.links
            ),
            "bullets": p.bullets,
        }
        for p in candidate.projects
    ]

    return {
        "name": b.name,
        "contact_tex": " \\textbar{} ".join(contact_parts),
        "summary": b.summary,
        "education": education,
        "skills": candidate.skills,
        "projects": projects,
        "experience": experience,
    }


def render_tex(candidate: Candidate, template: str = DEFAULT_TEMPLATE) -> str:
    return _env().get_template(template).render(**build_context(candidate))


# DOTALL：日志按 ~79 列折行，长路径会把这句拆到多行
_PAGES_RE = re.compile(r"Output written on .*?\((\d+) pages?", re.DOTALL)


def compile_pdf(tex_source: str, output_pdf: Path) -> RenderResult:
    """XeLaTeX 编译 tex 源码，产出 PDF 并返回页数。中间文件放 output 同级 .build/。"""
    if shutil.which("xelatex") is None:
        raise RenderError("找不到 xelatex，请安装 MacTeX / TeX Live")
    output_pdf = output_pdf.resolve()
    build_dir = output_pdf.parent / ".build"
    build_dir.mkdir(parents=True, exist_ok=True)
    tex_path = build_dir / f"{output_pdf.stem}.tex"
    tex_path.write_text(tex_source, encoding="utf-8")

    proc = subprocess.run(  # noqa: PLW1510 — returncode 手动检查以便附带日志
        ["xelatex", "-interaction=nonstopmode", "-halt-on-error",
         f"-output-directory={build_dir}", str(tex_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        tail = "\n".join(proc.stdout.splitlines()[-25:])
        raise RenderError(f"XeLaTeX 编译失败（日志见 {build_dir}）：\n{tail}")

    m = _PAGES_RE.search(proc.stdout)
    pages = int(m.group(1)) if m else 0
    shutil.copy(build_dir / f"{output_pdf.stem}.pdf", output_pdf)
    return RenderResult(pdf_path=output_pdf, pages=pages)


def render_pdf(
    candidate: Candidate, output_pdf: Path, template: str = DEFAULT_TEMPLATE
) -> RenderResult:
    return compile_pdf(render_tex(candidate, template), output_pdf)
