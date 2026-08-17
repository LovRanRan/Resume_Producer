"""存储层：data/<candidate_id>/candidate.json 本地持久化。"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .models import Candidate

CANDIDATE_FILE = "candidate.json"
MASTER_COPY = "master.md"


def data_dir() -> Path:
    """数据根目录。默认 ./data，可用 RESUME_DATA_DIR 覆盖（测试用）。"""
    return Path(os.environ.get("RESUME_DATA_DIR", "data"))


def save_candidate(candidate: Candidate, source_md: Path | None = None) -> Path:
    """保存 candidate；若给出源档案路径则一并存一份 master.md 副本。"""
    cdir = data_dir() / candidate.id
    cdir.mkdir(parents=True, exist_ok=True)
    path = cdir / CANDIDATE_FILE
    path.write_text(candidate.model_dump_json(indent=2), encoding="utf-8")
    if source_md is not None and source_md.resolve() != (cdir / MASTER_COPY).resolve():
        shutil.copy(source_md, cdir / MASTER_COPY)
    return path


def load_candidate(candidate_id: str) -> Candidate:
    path = data_dir() / candidate_id / CANDIDATE_FILE
    if not path.exists():
        raise FileNotFoundError(f"candidate 不存在：{candidate_id}（找不到 {path}）")
    return Candidate.model_validate_json(path.read_text(encoding="utf-8"))


def list_candidates() -> list[Candidate]:
    root = data_dir()
    if not root.exists():
        return []
    return [
        Candidate.model_validate_json((d / CANDIDATE_FILE).read_text(encoding="utf-8"))
        for d in sorted(root.iterdir())
        if (d / CANDIDATE_FILE).exists()
    ]
