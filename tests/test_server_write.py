import os

from iwiki_mcp import indexer, server


def _seed(tmp_path, monkeypatch, with_domain=True):
    b = tmp_path / "wiki"
    b.mkdir()
    if with_domain:
        (b / "backend" / ".iwiki").mkdir(parents=True)
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".iwiki.toml").write_text('read = ["backend"]\nwrite = "backend"\n')
    monkeypatch.setenv("IWIKI_BASE_DIR", str(b))
    monkeypatch.setenv("IWIKI_PROJECT_DIR", str(proj))
    monkeypatch.setenv("IWIKI_LLM_BASE_URL", "http://x/v1")
    monkeypatch.setenv("IWIKI_LLM_KEY", "k")
    monkeypatch.setenv("IWIKI_EMBED_DIMENSIONS", "2")
    monkeypatch.setattr(indexer, "embed_texts", lambda cfg, t: [[1.0, 0.0] for _ in t])
    return str(b), str(proj)


def test_write_page_indexes_and_logs(tmp_path, monkeypatch):
    b, _ = _seed(tmp_path, monkeypatch)
    md = "# Auth\n## Overview\nsummary\n## Flow\nlogin then token\n"
    out = server.wiki_write_page("backend", "auth", md)
    assert out["page"] == "backend/auth.md"
    assert out["indexed_chunks"] >= 1
    assert os.path.isfile(os.path.join(b, "backend", "auth.md"))
    assert os.path.isfile(os.path.join(b, "backend", ".iwiki", "log.jsonl"))


def test_write_rejects_deep_heading(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    out = server.wiki_write_page("backend", "bad", "# T\n### Too Deep\nx\n")
    assert "error" in out


def test_write_refuses_overwrite_without_force(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    md = "# Auth\n## Overview\no\n## Flow\nx\n"
    server.wiki_write_page("backend", "auth", md)
    out = server.wiki_write_page("backend", "auth", md)
    assert "error" in out and "exists" in out["error"]


def test_create_domain(tmp_path, monkeypatch):
    b, _ = _seed(tmp_path, monkeypatch, with_domain=False)
    out = server.wiki_create_domain("backend")
    assert out["created"] == "backend"
    assert os.path.isdir(os.path.join(b, "backend"))


def test_bind_writes_config(tmp_path, monkeypatch):
    _b, proj = _seed(tmp_path, monkeypatch)
    out = server.wiki_bind(read=["backend", "shared"], write="backend")
    assert out["read"] == ["backend", "shared"]
    assert 'write = "backend"' in open(os.path.join(proj, ".iwiki.toml")).read()
