# Decision: uv is the only package manager

**Date:** 2026-08-21  
**Status:** Accepted  
**Updated:** 2026-08-21 — Docker uses `uv.lock`, no `requirements.txt`

## Context

The project already has `pyproject.toml` and `uv.lock`. A second list (`requirements.txt`) for Docker would drift unless someone remembered to export after every lock change.

## Decision

- **uv** is the only package manager.
- Source of truth: `pyproject.toml` + `uv.lock`.
- There is no committed `requirements.txt`. Docker installs with `uv sync --frozen --no-dev` (venv at `/opt/venv` so a bind-mount of `/app` does not hide packages).
- Change dependencies with:

  ```bash
  uv add <package>
  uv remove <package>
  uv lock
  ```

## Consequences

- One lockfile, nothing to keep in sync.
- Images fail the build if `uv.lock` is missing or stale (`--frozen`).
- Optional extras (`dev` / `test`) are for local/CI only, not the image.
