from iwiki_mcp import indexer, retrieval, server


def _seed(tmp_path, monkeypatch):
    b = tmp_path / "wiki"
    (b / "backend" / ".iwiki").mkdir(parents=True)
    (b / "backend" / "auth.md").write_text(
        "# Auth\n## Overview\no\n## Token\nrefresh_token rotates\n"
    )
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".iwiki.toml").write_text('read = ["backend"]\nwrite = "backend"\n')
    monkeypatch.setenv("IWIKI_BASE_DIR", str(b))
    monkeypatch.setenv("IWIKI_PROJECT_DIR", str(proj))
    monkeypatch.setenv("IWIKI_LLM_BASE_URL", "http://x/v1")
    monkeypatch.setenv("IWIKI_LLM_KEY", "k")
    monkeypatch.setenv("IWIKI_EMBED_DIMENSIONS", "2")
    monkeypatch.setattr(indexer, "embed_texts", lambda cfg, t: [[1.0, 0.0] for _ in t])
    monkeypatch.setattr(retrieval, "embed_texts", lambda cfg, t: [[1.0, 0.0]])
    indexer.index_domain(
        __import__("iwiki_mcp.engine.config", fromlist=["Config"]).Config.load(),
        str(b),
        "backend",
    )
    return str(b)


def test_search_returns_results(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    out = server.wiki_search("token", scope="project", threshold=0.0)
    assert "results" in out and out["results"]
    assert out["results"][0]["domain"] == "backend"


def test_search_lexical_mode(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    out = server.wiki_search("refresh_token", mode="lexical")
    assert any(r["hit"] == "lexical" for r in out["results"])
