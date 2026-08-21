# Decision: uv is the only package manager

**Date:** 2026-08-21  
**Status:** Accepted

## Context

The project already has `pyproject.toml` and `uv.lock`. `requirements.txt` exists so Docker can `uv pip install -r requirements.txt`. Extra tools (pip, poetry, a hand-edited requirements file) would drift.

## Decision

- **uv** is the only package manager.
- Source of truth: `pyproject.toml` + `uv.lock`.
- `requirements.txt` is a generated export for Docker, not a second list of dependencies.
- After `uv add` / `uv remove` / `uv lock`:

  ```bash
  uv export --format requirements-txt --no-hashes -o requirements.txt
  ```

- Do not edit `requirements.txt` by hand.
- Docker keeps installing from that export (`uv pip install --system -r requirements.txt`). Switching the image to `uv sync` is not required for the MVP.

## Consequences

- One command sequence to change dependencies.
- CI can fail if the export is stale.
- Optional extras (`dev` / `test`) live only in `pyproject.toml` / `uv.lock`, not in the Docker export.
