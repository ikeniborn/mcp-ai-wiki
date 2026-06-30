import subprocess

from iwiki_mcp import server


def _seed(tmp_path, monkeypatch):
    b = tmp_path / "wiki"
    (b / "backend" / ".iwiki").mkdir(parents=True)
    (b / "backend" / "auth.md").write_text("# Auth\n## Overview\no\n## Flow\nx\n")
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".iwiki.toml").write_text('read = ["backend"]\nwrite = "backend"\n')
    monkeypatch.setenv("IWIKI_BASE_DIR", str(b))
    monkeypatch.setenv("IWIKI_PROJECT_DIR", str(proj))
    return str(b)


def test_lint_one_domain(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    out = server.wiki_lint("backend")
    assert "backend" in out["domains"]


def test_sync_no_repo(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    out = server.wiki_sync()
    assert "error" in out or "warning" in out
