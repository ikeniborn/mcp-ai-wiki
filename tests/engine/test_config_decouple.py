import pytest
from iwiki_mcp.engine.config import Config, ConfigError


def test_load_requires_api(monkeypatch):
    monkeypatch.delenv("IWIKI_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("IWIKI_LLM_KEY", raising=False)
    with pytest.raises(ConfigError):
        Config.load()


def test_load_does_not_read_cwd_ignore(monkeypatch, tmp_path):
    monkeypatch.setenv("IWIKI_LLM_BASE_URL", "http://x/v1")
    monkeypatch.setenv("IWIKI_LLM_KEY", "k")
    (tmp_path / ".iwikiignore").write_text("*.md\n")
    monkeypatch.chdir(tmp_path)
    cfg = Config.load()                      # default load_ignore=False
    assert cfg.ignore is None
    assert cfg.base_url == "http://x/v1"
