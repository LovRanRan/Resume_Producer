"""FastAPI 后端：档案 CRUD、tailor SSE 实时进度流、产出历史与文件服务。

鉴权：设置 RESUME_API_TOKEN 环境变量后所有 /api 路由要求
`Authorization: Bearer <token>`（文件类 GET 亦接受 `?token=`，供 iframe/下载用）。
未设置则不鉴权（本地开发）。CORS 白名单用 RESUME_CORS_ORIGINS（逗号分隔）。
"""

from __future__ import annotations

import json
import os
import queue
import threading
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from . import __version__
from .jd_input import JDInputError, jd_from_url
from .jobs import run_tailor_job
from .llm import LLMError
from .parser import ParseError, parse_master
from .renderer import RenderError, render_pdf
from .storage import data_dir, list_candidates, load_candidate, save_candidate


def _check_auth(request: Request) -> None:
    token = os.environ.get("RESUME_API_TOKEN")
    if not token:
        return
    header = request.headers.get("authorization", "")
    if header == f"Bearer {token}" or request.query_params.get("token") == token:
        return
    raise HTTPException(status_code=401, detail="unauthorized")


app = FastAPI(title="Resume Producer API", version=__version__, dependencies=[Depends(_check_auth)])

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "RESUME_CORS_ORIGINS", "http://localhost:3000,http://localhost:3001"
    ).split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_or_404(candidate_id: str):
    try:
        return load_candidate(candidate_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"candidate 不存在：{candidate_id}") from e


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__}


# ---------- 档案 ----------


class ImportRequest(BaseModel):
    markdown: str
    candidate_id: str | None = None


@app.get("/api/candidates")
def candidates():
    return [
        {
            "id": c.id,
            "name": c.basic.name,
            "education": len(c.education),
            "experience": len(c.experience),
            "projects": len(c.projects),
            "bullets": len(c.bullet_index()),
        }
        for c in list_candidates()
    ]


@app.post("/api/candidates")
def import_candidate(body: ImportRequest):
    try:
        candidate, warnings = parse_master(body.markdown, body.candidate_id)
    except ParseError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    save_candidate(candidate)
    (data_dir() / candidate.id / "master.md").write_text(body.markdown, encoding="utf-8")
    return {"id": candidate.id, "name": candidate.basic.name, "warnings": warnings}


@app.get("/api/candidates/{candidate_id}")
def candidate_detail(candidate_id: str):
    return _load_or_404(candidate_id).model_dump()


@app.get("/api/candidates/{candidate_id}/master", response_class=PlainTextResponse)
def get_master(candidate_id: str):
    path = data_dir() / candidate_id / "master.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="master.md 不存在")
    return path.read_text(encoding="utf-8")


@app.put("/api/candidates/{candidate_id}/master")
def put_master(candidate_id: str, body: ImportRequest):
    _load_or_404(candidate_id)
    try:
        candidate, warnings = parse_master(body.markdown, candidate_id)
    except ParseError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    save_candidate(candidate)
    (data_dir() / candidate_id / "master.md").write_text(body.markdown, encoding="utf-8")
    return {"id": candidate.id, "warnings": warnings, "bullets": len(candidate.bullet_index())}


@app.get("/api/candidates/{candidate_id}/render.pdf")
def render_full(candidate_id: str):
    candidate = _load_or_404(candidate_id)
    out = data_dir() / candidate_id / "full_render.pdf"
    try:
        render_pdf(candidate, out)
    except RenderError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return FileResponse(out, media_type="application/pdf")


# ---------- tailor（SSE） ----------


class TailorRequest(BaseModel):
    jd_text: str | None = None
    jd_url: str | None = None


@app.post("/api/candidates/{candidate_id}/tailor")
def tailor_stream(candidate_id: str, body: TailorRequest):
    candidate = _load_or_404(candidate_id)
    try:
        if body.jd_url:
            jd, jd_source = jd_from_url(body.jd_url), body.jd_url
        elif body.jd_text and body.jd_text.strip():
            jd, jd_source = body.jd_text.strip(), "网页粘贴"
        else:
            raise HTTPException(status_code=422, detail="需要 jd_text 或 jd_url")
    except JDInputError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    def events():
        q: queue.Queue[tuple[str, dict]] = queue.Queue()

        def work():
            try:
                job = run_tailor_job(
                    candidate, jd, jd_source,
                    progress=lambda msg: q.put(("progress", {"message": msg})),
                )
                q.put(("result", job.summary()))
            except (LLMError, RenderError) as e:
                q.put(("error", {"message": str(e)}))
            except Exception as e:  # noqa: BLE001 — 后台线程兜底，错误必须送回流
                q.put(("error", {"message": f"内部错误：{e}"}))

        threading.Thread(target=work, daemon=True).start()
        while True:
            kind, payload = q.get()
            yield f"data: {json.dumps({'type': kind, **payload}, ensure_ascii=False)}\n\n"
            if kind in ("result", "error"):
                return

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------- 产出历史 ----------

_ALLOWED_FILES = {
    "resume.pdf", "resume.tex", "report.md", "jd.txt",
    "jd_analysis.json", "selection.json", "rewrite.json",
}
_MEDIA_TYPES = {".pdf": "application/pdf", ".md": "text/markdown", ".json": "application/json"}


@app.get("/api/candidates/{candidate_id}/outputs")
def outputs(candidate_id: str):
    _load_or_404(candidate_id)
    root = data_dir() / candidate_id / "outputs"
    runs = []
    if root.exists():
        for d in sorted(root.iterdir(), reverse=True):
            if not (d / "resume.pdf").exists():
                continue
            meta = {}
            analysis = d / "jd_analysis.json"
            if analysis.exists():
                data = json.loads(analysis.read_text(encoding="utf-8"))
                meta = {"role_title": data.get("role_title"), "company": data.get("company")}
            runs.append({"run_id": d.name, **meta})
    return runs


@app.get("/api/candidates/{candidate_id}/outputs/{run_id}/{filename}")
def output_file(candidate_id: str, run_id: str, filename: str):
    if filename not in _ALLOWED_FILES or "/" in run_id or run_id.startswith("."):
        raise HTTPException(status_code=404, detail="not found")
    path = data_dir() / candidate_id / "outputs" / run_id / filename
    if not path.resolve().is_relative_to(data_dir().resolve()) or not path.exists():
        raise HTTPException(status_code=404, detail="not found")
    media = _MEDIA_TYPES.get(Path(filename).suffix, "text/plain")
    return FileResponse(path, media_type=media)
