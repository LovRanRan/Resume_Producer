"""渲染器测试：转义、上下文构建、（有 xelatex 时）真实编译。"""

import shutil
from pathlib import Path

import pytest

from resume_producer.parser import parse_master
from resume_producer.renderer import (
    _link_label,
    build_context,
    escape_tex,
    render_pdf,
    render_tex,
)

EXAMPLE = Path(__file__).parent.parent / "examples" / "candidate_example.md"


@pytest.fixture()
def example_candidate():
    candidate, _ = parse_master(EXAMPLE.read_text(encoding="utf-8"))
    return candidate


def test_escape_tex():
    assert escape_tex("A & B 100% #1_x") == r"A \& B 100\% \#1\_x"
    assert escape_tex("~2.9K LOC") == r"\textasciitilde{}2.9K LOC"
    assert escape_tex("FastAPI → SQS") == r"FastAPI $\rightarrow$ SQS"
    assert escape_tex("mypy --strict") == r"mypy -{}-strict"
    assert escape_tex("SQS/DynamoDB") == r"SQS/\allowbreak{}DynamoDB"
    # 单遍替换：转义引入的 { } \ 不会被二次转义
    assert escape_tex("\\x{y}") == r"\textbackslash{}x\{y\}"
    assert escape_tex(None) == ""


def test_link_label():
    assert _link_label("https://github.com/foo/bar", single=True) == "GitHub"
    assert _link_label("https://alexchen.example.dev", single=True) == "alexchen.example.dev"
    assert _link_label("https://github.com/foo/mcp-repo-mapper", single=False) == "mcp-repo-mapper"


def test_build_context(example_candidate):
    ctx = build_context(example_candidate)
    assert ctx["name"] == "Alex Chen"
    assert r"\href{mailto:alex.chen.example@gmail.com}" in ctx["contact_tex"]
    assert ctx["education"][0]["dates_line"] == "Jun 2024"
    assert ctx["experience"][0]["right"] == "Seattle, WA · Jun 2023 – Sep 2023"
    assert ctx["projects"][0]["links_tex"] == (
        r"\href{https://github.com/alexchen-example/queuectl}{GitHub}"
    )


def test_render_tex_contains_content(example_candidate):
    tex = render_tex(example_candidate)
    assert r"\documentclass" in tex
    assert "Alex Chen" in tex
    assert "queuectl" in tex
    assert r"\BLOCK" not in tex and r"\VAR" not in tex  # 模板全部展开


@pytest.mark.skipif(shutil.which("xelatex") is None, reason="需要 xelatex")
def test_compile_pdf(example_candidate, tmp_path):
    result = render_pdf(example_candidate, tmp_path / "out.pdf")
    assert result.pdf_path.exists()
    assert result.pages == 1  # 示例档案内容少，应为单页
