"""FastAPI 后端测试（tailor 用 mock，不调 LLM/LaTeX）。"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from resume_producer.api import app

EXAMPLE = Path(__file__).parent.parent / "examples" / "candidate_example.md"


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("RESUME_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("RESUME_API_TOKEN", raising=False)


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def imported(client):
    resp = client.post("/api/candidates", json={"markdown": EXAMPLE.read_text(encoding="utf-8")})
    assert resp.status_code == 200
    return resp.json()


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_import_and_list(client, imported):
    assert imported["id"] == "alex-chen"
    assert imported["warnings"] == []
    listed = client.get("/api/candidates").json()
    assert len(listed) == 1
    assert listed[0]["name"] == "Alex Chen"
    assert listed[0]["bullets"] == 5


def test_import_invalid_markdown(client):
    resp = client.post("/api/candidates", json={"markdown": "## Basic Info\nEmail: a@b.c\n"})
    assert resp.status_code == 422


def test_detail_and_master_roundtrip(client, imported):
    detail = client.get("/api/candidates/alex-chen").json()
    assert detail["basic"]["name"] == "Alex Chen"

    master = client.get("/api/candidates/alex-chen/master").text
    assert "## Basic Info" in master

    updated = master + "\n- Extra: Kafka, Flink\n"  # Skills section 末尾加一行
    resp = client.put("/api/candidates/alex-chen/master", json={"markdown": updated})
    assert resp.status_code == 200
    assert client.get("/api/candidates/alex-chen/master").text == updated


def test_missing_candidate_404(client):
    assert client.get("/api/candidates/nope").status_code == 404
    assert client.get("/api/candidates/nope/master").status_code == 404


def test_tailor_sse_stream(client, imported, monkeypatch):
    """SSE 流：mock 掉 run_tailor_job，验证进度事件 + 结果事件。"""

    class FakeJob:
        run_id = "20260101-000000-acme"
        out_dir = Path("/tmp/x")

        def summary(self):
            return {"run_id": self.run_id, "role_title": "SWE", "pages": 1}

    def fake_job(candidate, jd, jd_source, progress):
        progress("① JD 分析中…")
        progress("② 条目选择中…")
        return FakeJob()

    monkeypatch.setattr("resume_producer.api.run_tailor_job", fake_job)
    with client.stream(
        "POST", "/api/candidates/alex-chen/tailor", json={"jd_text": "some jd"}
    ) as resp:
        assert resp.status_code == 200
        events = [
            json.loads(line[len("data: "):])
            for line in resp.iter_lines()
            if line.startswith("data: ")
        ]
    assert [e["type"] for e in events] == ["progress", "progress", "result"]
    assert events[-1]["run_id"] == "20260101-000000-acme"


def test_tailor_requires_jd(client, imported):
    assert client.post("/api/candidates/alex-chen/tailor", json={}).status_code == 422


def test_outputs_listing_and_file_security(client, imported, tmp_path, monkeypatch):
    from resume_producer.storage import data_dir

    run = data_dir() / "alex-chen" / "outputs" / "20260101-000000-acme"
    run.mkdir(parents=True)
    (run / "resume.pdf").write_bytes(b"%PDF-1.4 fake")
    (run / "jd_analysis.json").write_text(
        json.dumps({"role_title": "SWE", "company": "Acme"}), encoding="utf-8"
    )
    (run / "report.md").write_text("# report", encoding="utf-8")

    runs = client.get("/api/candidates/alex-chen/outputs").json()
    assert runs == [{"run_id": "20260101-000000-acme", "role_title": "SWE", "company": "Acme"}]

    ok = client.get("/api/candidates/alex-chen/outputs/20260101-000000-acme/report.md")
    assert ok.status_code == 200 and ok.text == "# report"
    # 路径穿越 / 非白名单文件
    assert (
        client.get("/api/candidates/alex-chen/outputs/20260101-000000-acme/secret.txt").status_code
        == 404
    )
    assert (
        client.get("/api/candidates/alex-chen/outputs/..%2F..%2Fx/report.md").status_code == 404
    )


def test_auth_token(client, imported, monkeypatch):
    monkeypatch.setenv("RESUME_API_TOKEN", "s3cret")
    assert client.get("/api/candidates").status_code == 401
    assert (
        client.get("/api/candidates", headers={"Authorization": "Bearer s3cret"}).status_code
        == 200
    )
    assert client.get("/api/candidates?token=s3cret").status_code == 200
