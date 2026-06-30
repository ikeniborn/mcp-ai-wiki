---
review:
  plan_hash: 7e8052a5e6a53241
  spec_hash: 416bdf66544dc25a
  last_run: 2026-06-30
  phases:
    structure:     { status: passed }
    coverage:      { status: passed }
    dependencies:  { status: passed }
    verifiability: { status: passed }
    consistency:   { status: passed }
  findings:
    - id: F-001
      phase: coverage
      severity: WARNING
      section: "Task 1, Step 2 (tests/test_lock.py)"
      section_hash: 8f3b1c4e9a2d6705
      fragment: "test_base_lock_second_acquire_times_out_while_held"
      text: >-
        The spec Testing section requires "base_lock acquires/releases; a second acquire
        while held blocks then succeeds (thread or short-timeout assertion)". The plan's
        lock test only covers the "blocks (times out) while held" half via
        test_base_lock_second_acquire_times_out_while_held; it never asserts the "then
        succeeds" half — that a waiter acquires once the first holder releases.
      fix: >-
        Add a short assertion (thread- or sequence-based) that after the first lock is
        released a second base_lock(base).acquire() succeeds, to cover the spec's
        "blocks then succeeds" requirement.
      verdict: open
      verdict_at: null
    - id: F-002
      phase: verifiability
      severity: INFO
      section: "Task 6, Step 1"
      section_hash: 1d7a0e5c8b6f9243
      fragment: "# via the iwiki:iwiki-ingest skill, per CLAUDE.md docs-upkeep"
      text: >-
        Task 6 Step 1's ```bash``` fenced block contains only a comment, no runnable
        command; the actual actionable instruction (invoke iwiki:iwiki-ingest for the
        three sources, then /iwiki-lint and fix broken refs/orphans) lives in the prose
        around it. The DoD ("Fix any broken [[refs]]/orphans the lint reports") is
        verifiable, so this is cosmetic.
      fix: >-
        Drop the empty code fence and keep the skill-invocation instruction in prose,
        or replace the comment with the literal skill invocations to keep the step's
        command block runnable.
      verdict: open
      verdict_at: null
chain:
  intent: null
  spec: docs/superpowers/specs/2026-06-30-concurrent-sync-and-iwikiignore-design.md
---
# Concurrent base sync + `.iwikiignore` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the shared git base safe under parallel projects, and add a `.iwikiignore` source-path filter.

**Architecture:** Two independent fail-soft features. (1) An inter-process `filelock` on the base serializes git mutations; commits are scoped to the write-domain pathspec (no more `git add -A`), and `wiki_sync` retries `push` on non-fast-forward. (2) A gitignore-syntax `.iwikiignore` at the project root gates the `source=` argument of `wiki_write_page` and is auto-created (seeded from `.gitignore`) on domain init / project bind.

**Tech Stack:** Python ≥3.10, `mcp` (FastMCP), `filelock` (new), `pathspec` (existing), `subprocess` git, `pytest`.

## Global Constraints

- Python `>=3.10`; no new syntax above that floor.
- Every tool handler stays **fail-soft**: return a JSON-serializable dict; never raise out of `@_safe`. Helper modules (`sync`, `lock`, `ignore`) return dicts/values and translate their own expected errors.
- No linter/formatter configured — match surrounding style by hand (4-space indent, double quotes, `from __future__ import annotations`).
- Tests never hit the network: `monkeypatch` `indexer.embed_texts`, set dummy `IWIKI_*` env vars (pattern: `tests/test_server_write.py::_seed`). `pythonpath=["src"]`, `asyncio_mode="auto"` — import `iwiki_mcp` directly.
- New runtime dependency: `filelock`. `pathspec>=0.12` already present.
- `auto_commit`/`sync` timing params are plain function args with defaults — **not** routed through `Config.load` (must stay independent of the LLM-key stop rule).
- Docs/code comments/commit messages in English.

---

## File structure

- `src/iwiki_mcp/lock.py` — **new.** Thin `filelock` wrapper: `base_lock(base, timeout)`. Single responsibility: produce the base-level lock, ensure its directory.
- `src/iwiki_mcp/sync.py` — **modify.** `auto_commit` gains `pathspec`/`timeout` + lock + domain-scoped staging; `sync` gains `timeout`/`push_retries` + lock + push-retry.
- `src/iwiki_mcp/ignore.py` — **new.** `.iwikiignore` lifecycle: `ensure_iwikiignore`, `load_project_ignore`, `is_ignored`.
- `src/iwiki_mcp/server.py` — **modify.** Wire pathspec into the two `auto_commit` call sites; add the `source=` gate to `wiki_write_page`; call `ensure_iwikiignore` in `wiki_create_domain` and `wiki_bind`.
- `pyproject.toml` — **modify.** Add `filelock` to `dependencies`.
- `tests/test_lock.py`, `tests/test_sync_concurrency.py`, `tests/test_iwikiignore.py`, `tests/test_server_iwikiignore.py` — **new.**
- `docs/wiki/indexing.md` / `docs/wiki/architecture.md` — **modify** (docs-upkeep, final task).

Task order: lock (1) → auto_commit (2) → sync (3) → ignore (4) → server wiring (5) → docs (6).

---

### Task 1: `lock.py` — inter-process base lock

**Files:**
- Create: `src/iwiki_mcp/lock.py`
- Create (dep): `pyproject.toml` (add `filelock`)
- Test: `tests/test_lock.py`

**Interfaces:**
- Consumes: nothing (leaf module).
- Produces: `base_lock(base: str, timeout: float = 15.0) -> filelock.FileLock`. Lock file at `base/.iwiki/lock`; directory ensured. Acquire blocks up to `timeout`, then raises `filelock.Timeout`.

- [ ] **Step 1: Add the dependency**

Edit `pyproject.toml`, in `[project].dependencies`, add `filelock` after `pathspec`:

```toml
dependencies = [
    "mcp>=1.2.0",
    "httpx>=0.27",
    "pathspec>=0.12",
    "filelock>=3.12",
    "numpy>=1.26",
    "tomli>=2.0; python_version < '3.11'",
]
```

Then install:

```bash
uv sync --extra dev
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_lock.py`:

```python
import os

import pytest
from filelock import Timeout

from iwiki_mcp.lock import base_lock


def test_base_lock_creates_meta_dir_and_locks(tmp_path):
    base = str(tmp_path)
    lock = base_lock(base)
    assert os.path.isdir(os.path.join(base, ".iwiki"))
    with lock:
        assert lock.is_locked


def test_base_lock_second_acquire_times_out_while_held(tmp_path):
    base = str(tmp_path)
    with base_lock(base, timeout=15.0):
        with pytest.raises(Timeout):
            base_lock(base, timeout=0.1).acquire()


def test_base_lock_acquired_after_holder_releases(tmp_path):
    base = str(tmp_path)
    with base_lock(base):
        pass  # held, then released on block exit
    second = base_lock(base, timeout=1.0)
    with second:  # a fresh waiter acquires once the base is free
        assert second.is_locked
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_lock.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iwiki_mcp.lock'`.

- [ ] **Step 4: Write minimal implementation**

Create `src/iwiki_mcp/lock.py`:

```python
"""Inter-process lock for git mutations on the shared base.

Many iwiki-mcp servers (one per client session) can share one base repo.
This serializes all git index / push operations across processes."""
from __future__ import annotations

import os

from filelock import FileLock


def base_lock(base: str, timeout: float = 15.0) -> FileLock:
    """Return a FileLock guarding git mutations on `base`.

    The lock file lives at base/.iwiki/lock. base/.iwiki/ holds server
    metadata at the base level; it is never a domain (`.`-prefixed names are
    excluded by list_domains/domain_exists) and is never staged (commits are
    domain-scoped). Acquire blocks up to `timeout` seconds, then raises
    filelock.Timeout."""
    meta_dir = os.path.join(base, ".iwiki")
    os.makedirs(meta_dir, exist_ok=True)
    return FileLock(os.path.join(meta_dir, "lock"), timeout=timeout)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_lock.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/iwiki_mcp/lock.py tests/test_lock.py
git commit -m "feat: add inter-process base_lock (filelock)"
```

---

### Task 2: `auto_commit` — lock + domain-scoped staging

**Files:**
- Modify: `src/iwiki_mcp/sync.py` (the `auto_commit` function, lines 23-39, plus imports)
- Test: `tests/test_sync_concurrency.py`

**Interfaces:**
- Consumes: `lock.base_lock(base, timeout)` from Task 1.
- Produces: `auto_commit(base, message, pathspec: str | None = None, timeout: float = 15.0) -> dict`. With `pathspec`, stages and checks only `<pathspec>/`; `pathspec=None` keeps the old `add -A` behavior (back-compat for existing callers/tests). On lock timeout returns `{"committed": False, "warning": "base busy: lock timeout"}`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_sync_concurrency.py`:

```python
import subprocess

from iwiki_mcp import sync


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   capture_output=True, text=True)


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@t")
    _git(path, "config", "user.name", "t")


def test_auto_commit_pathspec_excludes_sibling_domain(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta").mkdir()
    (tmp_path / "alpha" / "a.md").write_text("a")
    (tmp_path / "beta" / "b.md").write_text("b")

    res = sync.auto_commit(str(tmp_path), "iwiki: ingest alpha/a.md", pathspec="alpha")

    assert res["committed"] is True
    committed = subprocess.run(
        ["git", "show", "--name-only", "--pretty=format:", "HEAD"],
        cwd=tmp_path, capture_output=True, text=True).stdout
    assert "alpha/a.md" in committed
    assert "beta/b.md" not in committed
    # beta is still untracked, not swept into the commit
    porcelain = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=tmp_path, capture_output=True, text=True).stdout
    assert "beta/b.md" in porcelain
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sync_concurrency.py::test_auto_commit_pathspec_excludes_sibling_domain -v`
Expected: FAIL — `auto_commit() got an unexpected keyword argument 'pathspec'`.

- [ ] **Step 3: Modify `sync.py` imports**

At the top of `src/iwiki_mcp/sync.py`, after the existing imports, add:

```python
from filelock import Timeout

from .lock import base_lock
```

- [ ] **Step 4: Replace `auto_commit`**

Replace the whole `auto_commit` function (lines 23-39) with:

```python
def auto_commit(base: str, message: str, pathspec: str | None = None,
                timeout: float = 15.0) -> dict:
    if not is_git_repo(base):
        return {"committed": False, "warning": "base is not a git repo; not committing"}
    scope = ("--", pathspec) if pathspec else ()
    try:
        with base_lock(base, timeout):
            add = _run(base, "add", *(("--", pathspec) if pathspec else ("-A",)))
            if add.returncode != 0:
                return {"committed": False, "warning": add.stderr.strip()}
            status = _run(base, "status", "--porcelain", *scope)
            if status.returncode != 0:
                return {"committed": False, "warning": status.stderr.strip()}
            if not status.stdout.strip():
                return {"committed": False, "warning": "nothing to commit"}
            r = _run(base, "commit", "-m", message)
            return {"committed": r.returncode == 0,
                    **({} if r.returncode == 0 else {"warning": r.stderr.strip()})}
    except Timeout:
        return {"committed": False, "warning": "base busy: lock timeout"}
    except Exception as e:
        return {"committed": False, "warning": str(e)}
```

Why this is safe: the lock is held across `add` → `status` → `commit`, so no other process stages between them. `git add -- <pathspec>` stages only the domain; `git status --porcelain -- <pathspec>` checks only the domain; `git commit` then commits exactly that staged content. A sibling domain's untracked/modified files are never captured.

- [ ] **Step 5: Run the new test + the existing sync suite**

Run: `uv run pytest tests/test_sync_concurrency.py tests/test_sync.py -v`
Expected: PASS. The existing `tests/test_sync.py` calls `auto_commit(base, msg)` with no `pathspec`, exercising the `-A` back-compat path — those must still pass.

- [ ] **Step 6: Commit**

```bash
git add src/iwiki_mcp/sync.py tests/test_sync_concurrency.py
git commit -m "feat: scope auto_commit to a domain pathspec under base_lock"
```

---

### Task 3: `sync` — lock + push-retry on non-fast-forward

**Files:**
- Modify: `src/iwiki_mcp/sync.py` (the `sync` function, lines 62-82; add `_is_non_ff` helper)
- Test: `tests/test_sync_concurrency.py` (append)

**Interfaces:**
- Consumes: `lock.base_lock` (Task 1).
- Produces: `sync(base, timeout: float = 15.0, push_retries: int = 3) -> dict`. Retries `pull --rebase` + `push` up to `push_retries` times when `push` is rejected non-fast-forward. Existing return keys unchanged (`pulled`, `pushed`, optional `warning`/`error`/`hint`).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sync_concurrency.py`:

```python
def test_sync_push_retry_on_non_fast_forward(tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(remote)],
                   check=True)

    base = tmp_path / "base"
    _init_repo(base)
    _git(base, "checkout", "-q", "-b", "main")
    (base / "a.md").write_text("1")
    sync.auto_commit(str(base), "c1")
    _git(base, "remote", "add", "origin", str(remote))
    _git(base, "push", "-q", "-u", "origin", "main")

    # A neighbor clone advances origin/main behind our back.
    nb = tmp_path / "nb"
    subprocess.run(["git", "clone", "-q", str(remote), str(nb)], check=True)
    _git(nb, "config", "user.email", "n@n")
    _git(nb, "config", "user.name", "n")
    (nb / "b.md").write_text("2")
    _git(nb, "add", "-A")
    _git(nb, "commit", "-q", "-m", "neighbor")
    _git(nb, "push", "-q", "origin", "main")

    # We commit locally on top of the now-stale main -> push is non-ff.
    (base / "c.md").write_text("3")
    sync.auto_commit(str(base), "c3")

    res = sync.sync(str(base))

    assert res["pushed"] is True
    log = subprocess.run(["git", "log", "--oneline"], cwd=base,
                         capture_output=True, text=True).stdout
    assert "neighbor" in log  # pull --rebase pulled the neighbor commit in
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sync_concurrency.py::test_sync_push_retry_on_non_fast_forward -v`
Expected: FAIL — the current `sync` pushes once, gets a non-ff rejection, returns `pushed: False` (no retry).

- [ ] **Step 3: Add the non-ff helper**

In `src/iwiki_mcp/sync.py`, after `_output` (line 59), add:

```python
def _is_non_ff(r: subprocess.CompletedProcess) -> bool:
    text = (r.stderr + r.stdout).lower()
    return any(s in text for s in ("non-fast-forward", "fetch first", "rejected"))
```

- [ ] **Step 4: Replace `sync`**

Replace the whole `sync` function (lines 62-82) with:

```python
def sync(base: str, timeout: float = 15.0, push_retries: int = 3) -> dict:
    if not is_git_repo(base):
        return {"pulled": False, "pushed": False, "error": "base is not a git repo"}
    try:
        with base_lock(base, timeout):
            if not _has_remote(base):
                return {"pulled": False, "pushed": False,
                        "warning": "no git remote configured; commits stay local"}
            for attempt in range(push_retries):
                pull = _run(base, "pull", "--rebase")
                if pull.returncode != 0:
                    if _has_rebase_state(base):
                        _run(base, "rebase", "--abort")
                        return {"pulled": False, "pushed": False,
                                "error": "pull --rebase conflict (aborted)",
                                "hint": "resolve in the base repo, or re-run index to "
                                        "regenerate a conflicted .iwiki/index.jsonl, "
                                        "then sync again"}
                    return {"pulled": False, "pushed": False, "error": _output(pull)}
                push = _run(base, "push")
                if push.returncode == 0:
                    return {"pulled": True, "pushed": True}
                if _is_non_ff(push) and attempt < push_retries - 1:
                    continue
                return {"pulled": True, "pushed": False, "warning": push.stderr.strip()}
            return {"pulled": True, "pushed": False, "warning": "push retries exhausted"}
    except Timeout:
        return {"pulled": False, "pushed": False, "warning": "base busy: lock timeout"}
    except Exception as e:
        return {"pulled": False, "pushed": False, "error": str(e)}
```

- [ ] **Step 5: Run the new test + the existing sync suite**

Run: `uv run pytest tests/test_sync_concurrency.py tests/test_sync.py -v`
Expected: PASS. `test_sync_no_remote_warns` and `test_sync_pull_failure_preserves_non_conflict_error` still pass (no-remote → warning; missing-remote pull failure with no rebase-state → `error` preserved, not the conflict string).

- [ ] **Step 6: Commit**

```bash
git add src/iwiki_mcp/sync.py tests/test_sync_concurrency.py
git commit -m "feat: retry push on non-fast-forward under base_lock"
```

---

### Task 4: `ignore.py` — `.iwikiignore` lifecycle

**Files:**
- Create: `src/iwiki_mcp/ignore.py`
- Test: `tests/test_iwikiignore.py`

**Interfaces:**
- Consumes: `engine.config._load_ignore(filename) -> PathSpec | None` (existing; compiles gitignore-style, returns None for comment/blank-only files).
- Produces:
  - `ensure_iwikiignore(project_dir: str) -> bool` — creates `project_dir/.iwikiignore` if absent (seeded from secret defaults + a one-time copy of `.gitignore`); returns True iff created; idempotent.
  - `load_project_ignore(project_dir: str) -> PathSpec | None`.
  - `is_ignored(spec: PathSpec | None, source: str, project_dir: str) -> bool`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_iwikiignore.py`:

```python
import os

from iwiki_mcp import ignore


def test_ensure_creates_with_secret_defaults(tmp_path):
    created = ignore.ensure_iwikiignore(str(tmp_path))
    assert created is True
    text = (tmp_path / ".iwikiignore").read_text()
    assert ".env" in text
    assert "*secret*" in text


def test_ensure_is_idempotent(tmp_path):
    (tmp_path / ".iwikiignore").write_text("custom\n")
    created = ignore.ensure_iwikiignore(str(tmp_path))
    assert created is False
    assert (tmp_path / ".iwikiignore").read_text() == "custom\n"


def test_ensure_seeds_from_gitignore(tmp_path):
    (tmp_path / ".gitignore").write_text("build/\n*.log\n")
    ignore.ensure_iwikiignore(str(tmp_path))
    text = (tmp_path / ".iwikiignore").read_text()
    assert "build/" in text
    assert "*.log" in text


def test_is_ignored_matches_inside_project(tmp_path):
    (tmp_path / ".iwikiignore").write_text(".env\nsecrets/**\n")
    spec = ignore.load_project_ignore(str(tmp_path))
    assert ignore.is_ignored(spec, str(tmp_path / ".env"), str(tmp_path)) is True
    assert ignore.is_ignored(spec, str(tmp_path / "secrets" / "k.txt"),
                             str(tmp_path)) is True
    assert ignore.is_ignored(spec, str(tmp_path / "src" / "main.py"),
                             str(tmp_path)) is False


def test_is_ignored_outside_project_matches_basename(tmp_path):
    (tmp_path / ".iwikiignore").write_text("*.key\n")
    spec = ignore.load_project_ignore(str(tmp_path))
    outside = tmp_path.parent / "elsewhere" / "id.key"
    assert ignore.is_ignored(spec, str(outside), str(tmp_path)) is True


def test_load_returns_none_when_absent(tmp_path):
    assert ignore.load_project_ignore(str(tmp_path)) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_iwikiignore.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'iwiki_mcp.ignore'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/iwiki_mcp/ignore.py`:

```python
"""`.iwikiignore` -- a gitignore-syntax filter at the project root.

Keeps secret / noise source paths out of the wiki. Created (seeded from
.gitignore) when a domain is initialized or a project binds; enforced as a
gate on the `source=` argument of wiki_write_page. The server reads only
.iwikiignore at runtime; the .gitignore copy is a one-time seed."""
from __future__ import annotations

import os

from pathspec import PathSpec

from .engine.config import _load_ignore

_DEFAULT = """\
# .iwikiignore -- source paths that must NOT be ingested into the wiki.
# gitignore syntax. Seeded from .gitignore plus secret defaults; edit freely.

# --- secrets (default) ---
.env
.env.*
*.key
*.pem
*.p12
*secret*
*credentials*
"""


def ensure_iwikiignore(project_dir: str) -> bool:
    """Create project_dir/.iwikiignore if absent. Idempotent.
    Returns True iff a file was created."""
    path = os.path.join(project_dir, ".iwikiignore")
    if os.path.exists(path):
        return False
    content = _DEFAULT
    gitignore = os.path.join(project_dir, ".gitignore")
    if os.path.exists(gitignore):
        with open(gitignore, encoding="utf-8") as fh:
            inherited = fh.read()
        if not inherited.endswith("\n"):
            inherited += "\n"
        content += "\n# --- inherited from .gitignore ---\n" + inherited
    os.makedirs(project_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return True


def load_project_ignore(project_dir: str) -> PathSpec | None:
    """Compile project_dir/.iwikiignore. None if absent or only comments/blanks."""
    return _load_ignore(os.path.join(project_dir, ".iwikiignore"))


def is_ignored(spec: PathSpec | None, source: str, project_dir: str) -> bool:
    """True if source matches spec. Inside project_dir -> relpath match;
    outside -> basename match. spec None / empty source -> False."""
    if spec is None or not source:
        return False
    abs_source = os.path.abspath(source)
    rel = os.path.relpath(abs_source, os.path.abspath(project_dir))
    if rel.startswith(".."):
        rel = os.path.basename(abs_source)
    return spec.match_file(rel)
```

Note: `_load_ignore` takes a full path and itself guards `os.path.exists`; reusing it keeps the gitignore-compile logic DRY and avoids triggering `Config.load`'s LLM stop-rule.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_iwikiignore.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/iwiki_mcp/ignore.py tests/test_iwikiignore.py
git commit -m "feat: add .iwikiignore lifecycle (ensure/load/match)"
```

---

### Task 5: `server.py` wiring — gate + pathspec + ensure

**Files:**
- Modify: `src/iwiki_mcp/server.py` (imports line 15; `wiki_write_page`; `wiki_create_domain`; `wiki_bind`)
- Test: `tests/test_server_iwikiignore.py`

**Interfaces:**
- Consumes: `ignore.load_project_ignore`, `ignore.is_ignored`, `ignore.ensure_iwikiignore` (Task 4); `sync.auto_commit(..., pathspec=)` (Task 2).
- Produces: no new public surface — behavior changes on existing tools (`wiki_write_page` rejects ignored `source`; `wiki_create_domain`/`wiki_bind` create `.iwikiignore`; both `auto_commit` calls pass `pathspec`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_server_iwikiignore.py`:

```python
import os

from iwiki_mcp import indexer, server

# Reuse the established seed pattern.
from tests.test_server_write import _seed


def test_write_page_rejects_ignored_source(tmp_path, monkeypatch):
    b, proj = _seed(tmp_path, monkeypatch)
    open(os.path.join(proj, ".iwikiignore"), "w").write(".env\n")
    secret = os.path.join(proj, ".env")
    open(secret, "w").write("TOKEN=1")

    md = "# Auth\n## Overview\no\n## Flow\nx\n"
    out = server.wiki_write_page("backend", "auth", md, source=secret)

    assert "error" in out
    assert "iwikiignore" in out["error"]
    assert not os.path.exists(os.path.join(b, "backend", "auth.md"))


def test_write_page_allows_non_ignored_source(tmp_path, monkeypatch):
    b, proj = _seed(tmp_path, monkeypatch)
    open(os.path.join(proj, ".iwikiignore"), "w").write(".env\n")
    src = os.path.join(proj, "src.py")
    open(src, "w").write("x = 1")

    md = "# Auth\n## Overview\no\n## Flow\nx\n"
    out = server.wiki_write_page("backend", "auth", md, source=src)

    assert out.get("page") == "backend/auth.md"
    assert os.path.isfile(os.path.join(b, "backend", "auth.md"))


def test_create_domain_creates_iwikiignore(tmp_path, monkeypatch):
    b, proj = _seed(tmp_path, monkeypatch, with_domain=False)
    server.wiki_create_domain("backend")
    assert os.path.isfile(os.path.join(proj, ".iwikiignore"))


def test_bind_creates_iwikiignore(tmp_path, monkeypatch):
    b, proj = _seed(tmp_path, monkeypatch)
    os.makedirs(os.path.join(b, "shared", ".iwiki"))
    server.wiki_bind(read=["backend", "shared"], write="backend")
    assert os.path.isfile(os.path.join(proj, ".iwikiignore"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server_iwikiignore.py -v`
Expected: FAIL — `wiki_write_page` does not reject (writes the page); `.iwikiignore` not created.

- [ ] **Step 3: Add the import**

In `src/iwiki_mcp/server.py`, change line 15 from:

```python
from . import base, indexer, retrieval, sync
```

to:

```python
from . import base, ignore, indexer, retrieval, sync
```

- [ ] **Step 4: Add the gate to `wiki_write_page`**

In `wiki_write_page`, immediately after the `blocking` check block (the `if blocking:` return, ending at line 251), before `path = _page_path(...)`, insert:

```python
    if source:
        spec = ignore.load_project_ignore(bind.project_dir)
        if ignore.is_ignored(spec, source, bind.project_dir):
            return {
                "error": "source matches .iwikiignore",
                "hint": f"'{source}' is excluded by .iwikiignore; "
                        "remove the pattern to ingest, or omit source",
            }
```

- [ ] **Step 5: Pass `pathspec` at the `wiki_write_page` commit**

In `wiki_write_page`, change the commit line (currently line 288):

```python
    commit = sync.auto_commit(bind.base, f"iwiki: ingest {page_rel}")
```

to:

```python
    commit = sync.auto_commit(bind.base, f"iwiki: ingest {page_rel}",
                              pathspec=valid_domain)
```

- [ ] **Step 6: Update `wiki_create_domain`**

Replace the body of `wiki_create_domain` after the `dom_path.is_dir()` guard (lines 326-328) with:

```python
    os.makedirs(dom_path / ".iwiki", exist_ok=True)
    ignore.ensure_iwikiignore(bind.project_dir)
    commit = sync.auto_commit(bind.base, f"iwiki: create domain {valid_domain}",
                              pathspec=valid_domain)
    return {"created": valid_domain, "committed": commit.get("committed", False)}
```

- [ ] **Step 7: Update `wiki_bind`**

In `wiki_bind`, after `base.write_project_config(...)` (line 347) and before `new = base.resolve_binding()`, insert:

```python
    ignore.ensure_iwikiignore(bind.project_dir)
```

- [ ] **Step 8: Run the new test + the full server write suite**

Run: `uv run pytest tests/test_server_iwikiignore.py tests/test_server_write.py -v`
Expected: PASS. Existing `test_create_domain`, `test_bind_writes_config`, `test_write_page_indexes_and_logs` still pass (the new behaviors are additive; `auto_commit` runs against a non-repo tmp base → fail-soft warning, `created`/`page` unaffected).

- [ ] **Step 9: Run the whole suite**

Run: `uv run pytest -q`
Expected: PASS (all tests).

- [ ] **Step 10: Commit**

```bash
git add src/iwiki_mcp/server.py tests/test_server_iwikiignore.py
git commit -m "feat: gate writes on .iwikiignore, auto-create it, scope commits"
```

---

### Task 6: Docs upkeep

**Files:**
- Modify: `docs/wiki/indexing.md` and/or `docs/wiki/architecture.md`

**Interfaces:** none (documentation).

- [ ] **Step 1: Regenerate the affected wiki pages**

The base-sync / git behavior is documented in `docs/wiki/architecture.md` (git best-effort) and the ignore/config behavior in `docs/wiki/indexing.md`. Update them for: `base_lock`, domain-scoped commits, push-retry, and the `.iwikiignore` source gate + auto-creation.

Use the iwiki skills (do not guess engine subcommands), per CLAUDE.md docs-upkeep — invoke `iwiki:iwiki-ingest` for each changed source, then `/iwiki-lint`:

1. `iwiki:iwiki-ingest src/iwiki_mcp/sync.py`
2. `iwiki:iwiki-ingest src/iwiki_mcp/lock.py`
3. `iwiki:iwiki-ingest src/iwiki_mcp/ignore.py`
4. `/iwiki-lint` — fix any broken `[[refs]]` / orphans it reports.

- [ ] **Step 2: Commit**

```bash
git add docs/wiki
git commit -m "docs: wiki for base_lock, domain-scoped commits, .iwikiignore"
```

---

## Self-Review

**1. Spec coverage:**
- Inter-process `filelock` lock on `base/.iwiki/lock` → Task 1. ✓
- `auto_commit` lock + domain pathspec (replace `add -A`) → Task 2. ✓
- `sync` lock + push-retry on non-ff, rebase-abort preserved → Task 3. ✓
- `ensure_iwikiignore` (seed from `.gitignore` + secret defaults, idempotent), `load_project_ignore`, `is_ignored` (relpath inside / basename outside) → Task 4. ✓
- `source=` gate in `wiki_write_page` (before transaction) → Task 5 steps 4. ✓
- pathspec at both `auto_commit` call sites → Task 5 steps 5-6. ✓
- `ensure_iwikiignore` in `wiki_create_domain` **and** `wiki_bind` → Task 5 steps 6-7. ✓
- `filelock` dependency → Task 1 step 1. ✓
- Timing params as function args, not `Config.load` → Tasks 2-3 signatures. ✓
- Docs upkeep → Task 6. ✓
- Out of scope (same-domain concurrent writes, source scanning, index removal) → not implemented, by design. ✓

**2. Placeholder scan:** No TBD/TODO; every code step shows full code; Task 6 names exact files and the skill to invoke. ✓

**3. Type consistency:** `base_lock(base, timeout=15.0)` used identically in Tasks 2-3. `auto_commit(base, message, pathspec=None, timeout=15.0)` defined in Task 2, called with `pathspec=valid_domain` in Task 5. `ensure_iwikiignore`/`load_project_ignore`/`is_ignored` signatures defined in Task 4, called with matching args in Task 5. `_is_non_ff` defined and used within Task 3. ✓
