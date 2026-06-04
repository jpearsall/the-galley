# CLAUDE.md

## What this repo is

A data-refresh pipeline for The Galley, a gluten-free/dairy-free meal planner. The app shell (HTML/JS) never changes — only `data/galley-data.json` is updated on a weekly cadence. The generator calls Claude with web search to re-verify product availability, validates the output against a strict JSON Schema, checks referential integrity, and publishes only if everything passes. A bad generation is rejected; the previous good file stays live.

## Project layout

| Path | Role |
|------|------|
| `scripts/generate.py` | The only script — refresh, validate, publish |
| `data/galley-data.json` | Single source of truth for the app |
| `schema/galley.schema.json` | JSON Schema the data must satisfy |
| `.github/workflows/refresh.yml` | Runs every Sunday 14:00 UTC, commits updated JSON |
| `k8s/cronjob.yml` | Kubernetes alternative (requires a built image) |
| `Dockerfile` | uv-based multi-stage build for the k8s path |
| `TODO.md` | Open work, mirrored as GitHub issues #1–#7 |

## Running locally

```bash
# Validate the current data file (no API call)
uv run python scripts/generate.py --check

# Call the API + validate, but don't write
ANTHROPIC_API_KEY=... uv run python scripts/generate.py --dry-run

# Full refresh (atomic write, validated)
ANTHROPIC_API_KEY=... uv run python scripts/generate.py
```

## Environment variables

| Var | Default | Notes |
|-----|---------|-------|
| `ANTHROPIC_API_KEY` | — | Required for API calls; not needed for `--check` |
| `GALLEY_MODEL` | `claude-sonnet-4-6` | Model used by the generator |
| `GALLEY_DATA` | `data/galley-data.json` | Overridden to `/data/galley-data.json` by the k8s CronJob |
| `GALLEY_SCHEMA` | `schema/galley.schema.json` | Path to the JSON Schema |

## What the generator will and won't change

**Will:** refresh product picks in `catalog`, swap discontinued items for current GF/DF equivalents, reorder the rotation, bump `updated`.

**Won't:** redesign macros (`targets`), change appliances, alter active-minute values, or touch the meal engineering in `meals`/`plan`/`batch`.

## Validation

Two layers run on every candidate before it is written:

1. **JSON Schema** — `schema/galley.schema.json` (draft 2020-12)
2. **Referential integrity** — every id in `plan`, `rotation`, and `shop` must resolve to a key in `catalog` or `meals`

## Branching

Primary branch: `main`. All changes go on a feature branch; open a PR into `main`.

## GitHub

Repo: `https://github.com/jpearsall/the-galley`
Open issues: `gh issue list --repo jpearsall/the-galley`
