"""存储层 roundtrip 测试。"""

from pathlib import Path

import pytest

from resume_producer.parser import parse_master
from resume_producer.storage import list_candidates, load_candidate, save_candidate

EXAMPLE = Path(__file__).parent.parent / "examples" / "candidate_example.md"


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("RESUME_DATA_DIR", str(tmp_path / "data"))


def test_roundtrip():
    candidate, _ = parse_master(EXAMPLE.read_text(encoding="utf-8"))
    path = save_candidate(candidate, source_md=EXAMPLE)
    assert path.exists()
    assert (path.parent / "master.md").exists()

    loaded = load_candidate(candidate.id)
    assert loaded == candidate


def test_list_candidates():
    assert list_candidates() == []
    candidate, _ = parse_master(EXAMPLE.read_text(encoding="utf-8"))
    save_candidate(candidate)
    assert [c.id for c in list_candidates()] == ["alex-chen"]


def test_load_missing_raises():
    with pytest.raises(FileNotFoundError):
        load_candidate("nope")
