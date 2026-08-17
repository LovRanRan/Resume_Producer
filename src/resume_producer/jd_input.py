"""JD 输入：文本 / 本地文件 / URL 抓取（尽力而为）。"""

from __future__ import annotations

from pathlib import Path

MIN_JD_CHARS = 100


class JDInputError(RuntimeError):
    pass


def jd_from_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise JDInputError(f"JD 文件为空：{path}")
    return text


def jd_from_url(url: str) -> str:
    """抓取 URL 正文。很多招聘站反爬/需登录，失败时提示用户改用粘贴。"""
    import httpx
    from bs4 import BeautifulSoup

    try:
        resp = httpx.get(
            url,
            follow_redirects=True,
            timeout=20,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
                )
            },
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise JDInputError(f"抓取失败（{e}）。请把 JD 文本粘贴或存成文件后用 --jd-file。") from e

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = "\n".join(
        line.strip() for line in soup.get_text("\n").splitlines() if line.strip()
    )
    if len(text) < MIN_JD_CHARS:
        raise JDInputError(
            "抓取到的正文过短（可能被反爬/需登录）。请把 JD 文本粘贴或用 --jd-file。"
        )
    return text
