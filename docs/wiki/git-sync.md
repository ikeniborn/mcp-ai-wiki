# Git sync of the base

## Overview
`sync.py` keeps the shared wiki base in git: it auto-commits after successful writes and offers an explicit pull-rebase-push sync. Every operation is fail-soft — a non-repo base or a missing remote degrades to a warning in the result dict, never an exception. This is what lets a wiki base travel between machines and projects. Invoked by [[mcp-server#Write path]] and the `wiki_sync` tool.

## Inter-process locking
`lock.py` provides `base_lock(base, timeout=15.0)`, a `FileLock` (from the `filelock` package) that guards all git mutations on the shared base. The lock file lives at `base/.iwiki/lock`. Because many `iwiki-mcp` servers (one per client session) can share one base git repo, all `git add`/`commit`/`push` operations must be serialized across processes. Acquiring the lock blocks up to `timeout` seconds; on `filelock.Timeout` every caller in `sync.py` returns `{"warning": "base busy: lock timeout"}` without raising.

## Auto-commit on write
`auto_commit(base, message, pathspec=None, timeout=15.0)` stages and commits after a page write or domain create, holding `base_lock` for the duration. When `pathspec` is set (the domain name), it runs `git add -- <domain>` instead of `git add -A`, scoping the staged changes to that domain only and keeping unrelated working-tree changes out of the commit. It then checks `git status --porcelain -- <domain>` and commits only when there is something to commit. The result reports `committed` (bool) plus a `warning` on any non-success: a non-repo base returns `committed: false` with a note, so the on-disk write still succeeds even when git does not. A lock timeout also returns `committed: false` with `"base busy: lock timeout"`.

## Explicit sync
`sync(base, timeout=15.0, push_retries=3)` shares the base with a remote, holding `base_lock` for the entire pull-push sequence. It runs `git pull --rebase` then `git push`, retrying the pull-push cycle up to `push_retries` times (default 3) on a non-fast-forward rejection (`_is_non_ff` detects "non-fast-forward", "fetch first", or "rejected" in git output). With no remote it warns that commits stay local. If the rebase conflicts it aborts (`git rebase --abort`) and returns an `error` plus a `hint` to resolve manually — re-running `wiki_index` regenerates a conflicted `.iwiki/index.jsonl` (see [[indexing#Index domain]]). On lock timeout it returns `{"pulled": false, "pushed": false, "warning": "base busy: lock timeout"}`. It returns `pulled` and `pushed` flags.

## Repository detection
All git calls go through `_run`, which shells out with `git -C base` and a timeout, capturing output. `is_git_repo` tests `rev-parse --is-inside-work-tree`; `_has_remote` checks `git remote`; `_has_rebase_state` looks for a `rebase-merge`/`rebase-apply` dir to detect an in-progress rebase before aborting. Wrapping subprocess errors keeps the module from ever raising into [[mcp-server#Error handling]].
