# Installing and registering iwiki-mcp

## Overview
How to install the `iwiki-mcp` server and wire it into Claude Code or Codex. Covers the global (`uv tool install`) and from-source (`uv sync`) install paths, the required `IWIKI_LLM_*` embeddings env, per-client registration of the stdio server, and appending the `templates/` agent snippets. After registration the client spawns `iwiki-mcp` over stdio and resolves project context via [[base-binding#Resolving the binding]].

## Purpose
Registration is the boundary between a published Python package and a working MCP tool surface. The server is not a daemon: the MCP client launches `iwiki-mcp` over stdio at session start and it lives for that session. Getting the executable on `PATH`, the embeddings credentials into the client env, and the agent snippet into project memory is what makes the [[mcp-server#Tool surface]] callable.

## Install paths
Requires Python `>=3.10`; `uv` is recommended, `pipx` is a drop-in alternative. The package is **not on PyPI yet**, so the global install runs from a local checkout: `uv tool install .` (or `pipx install .`) from the repo root, which lands an `iwiki-mcp` executable on `PATH`. `uv tool install iwiki-mcp` only works once the package is published. For development, `uv sync --extra dev` then `uv run pytest -q`; `uv run iwiki-mcp` runs the server from the checkout without a global install. The `iwiki-mcp` entry point is declared in `pyproject.toml` `[project.scripts]` → `iwiki_mcp.server:main`.

## Required environment
`iwiki-mcp` needs an OpenAI-compatible embeddings endpoint. Set `IWIKI_LLM_BASE_URL` (usually ending in `/v1`) and `IWIKI_LLM_KEY` in the MCP client env, plus `IWIKI_BASE_DIR` for the shared base. Keep `IWIKI_LLM_KEY` out of committed project files. These map to the loader in [[indexing#Configuration]]; the base resolution is described in [[base-binding#Resolving the binding]].

## Register in Claude Code
Confirm `iwiki-mcp --help` resolves, then register with `claude mcp add iwiki --env IWIKI_LLM_BASE_URL=... --env IWIKI_LLM_KEY=... --env IWIKI_BASE_DIR=... -- iwiki-mcp`, or add an equivalent `mcpServers.iwiki` block to `.mcp.json`. Verify with `claude mcp list` and `/mcp` in-session. Claude Code launches the server with `cwd` at the project root, so `.iwiki.toml` is picked up automatically.

## Register in Codex
Confirm `iwiki-mcp --help`, then add an `[mcp_servers.iwiki]` table to `~/.codex/config.toml` with `command = "iwiki-mcp"` and the same `env`, and restart Codex. Codex does not set the server `cwd` to the project, so pass `iwiki-mcp --project /abs/path` or set `IWIKI_PROJECT_DIR` in `env` when the launch dir differs from the project root — that is how `.iwiki.toml` is resolved by [[base-binding#Resolving the binding]].

## Agent instructions
Registration exposes the tools but not *when* to call them. The repo ships `templates/CLAUDE.md.snippet` and `templates/AGENTS.md.snippet` — append the matching one to the project's `CLAUDE.md` (Claude Code) or `AGENTS.md` (Codex). Both instruct the agent to `wiki_search` before a task, bootstrap a write-target, author pages after functionality changes, and `wiki_sync` at end of session. The snippets reference `.iwiki.toml`, so bind the project first via [[base-binding#Writing .iwiki.toml]].
