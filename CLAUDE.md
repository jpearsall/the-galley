# CLAUDE.md — The Galley

## What this is

A personal gluten-free / dairy-free meal system, in two parts:

1. **`index.html`** — a self-contained single-file web app with three tabs:
   - **Order**: rotating ready-made entrées + snacks (4- or 6-week loop, auto-detects current week)
   - **Eat**: daily meal plan with macros + per-meal appliance & hands-on-minutes tags
   - **Shop**: Sunday-to-Sunday grocery list with Walmart/Instacart links + Instacart bulk-add copy
   Has an Auto/Light/Dark theme toggle. Fetches `data/galley-data.json` on load; persists state via `localStorage`.

2. **`galley-pipeline/`** — a cron job that refreshes the app's data weekly. The app shell never regenerates; only `data/galley-data.json` does.

## Project layout

| Path | Role |
|------|------|
| `index.html` | Self-contained app shell — served by GitHub Pages |
| `scripts/generate.py` | The only pipeline script — refresh, validate, publish |
| `data/galley-data.json` | Single source of truth for the app |
| `schema/galley.schema.json` | JSON Schema the data must satisfy |
| `.github/workflows/refresh.yml` | Runs every Sunday 14:00 UTC, commits updated JSON |
| `k8s/cronjob.yml` | Kubernetes alternative (requires a built image) |
| `Dockerfile` | uv-based multi-stage build for the k8s path |
| `TODO.md` | Open work, mirrored as GitHub issues #1–#7 |

## Data model

All food data lives in one JSON file so nothing drifts:

| Key | Role |
|-----|------|
| `catalog` | Every product (entrées + snacks), defined once, referenced everywhere |
| `meals` | Composed plates; each has `appliance` + `active` (hands-on minutes) |
| `batch` | Sunday batch-cook playbook, per week (A/B) |
| `rotation` | 4–6 week ready-made loop (references catalog ids) |
| `plan` | 7-day meal plan, weeks A & B (references meals + snack catalog ids) |
| `shop` | Grocery categories; packaged items use `ref` into catalog, fresh items inline |
| `targets` | Daily macro targets (calories, protein, etc.) — never touched by the generator |

## Design constraints (do not break)

- Every item must be plausibly **gluten-free AND dairy-free**.
- Lands ~2,400–2,600 kcal/day, ~180g protein. Under the 2,800–3,200 target is fine (user's call).
- **Minimize active cooking time / mental effort.** Appliances only: rice cooker, Instant Pot, air fryer, crockpot, microwave, blender, or no-cook. No stovetop-heavy, multi-step dishes.
- Batch once on Sunday (~20–25 min), then ~13–18 min hands-on per day.
- Week A = ground turkey + eggs + turkey chili; Week B = crockpot chicken thighs + fresh air-fryer salmon (salmon is the one thing cooked fresh, not batched).
- Coconut aminos instead of soy; pea/rice protein instead of whey.

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

## Invariants for future edits

- Keep DATA separate from PRESENTATION.
- NEVER commit API keys — use the GitHub Actions secret only.
- When refreshing data, preserve the macro/appliance/effort design; only swap product picks.
- Validate before publishing.

## Branching

Primary branch: `main`. All changes go on a feature branch; open a PR into `main`.

## GitHub

Repo: `https://github.com/jpearsall/the-galley`
Open issues: `gh issue list --repo jpearsall/the-galley`
