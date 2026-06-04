# The Galley — auto-refresh pipeline

Keeps the app's **data** current on a weekly cadence without ever regenerating the
app itself. The app shell (HTML/JS) is fixed; only `data/galley-data.json` changes.

```
  ┌─ cron (Sun 14:00 UTC) ─┐
  │  GitHub Actions         │
  └───────────┬─────────────┘
              ▼
      scripts/generate.py
       ├─ calls Claude API (web_search) to re-verify products & refresh picks
       ├─ validates output against schema/galley.schema.json
       ├─ checks referential integrity (every id used actually exists)
       └─ streams response (max_tokens=32000) — rejects output if invalid
              ▼
      opens bot/data-refresh-DATE PR → CI validates → auto-merge → Pages redeploys
```

Why it's built this way: LLM-generated *markup* drifts and breaks. LLM-generated
*data*, validated against a strict schema, doesn't — a bad generation is rejected
and the previous good file stays live.

## Files

|Path                             |Role                                                      |
|---------------------------------|----------------------------------------------------------|
|`index.html`                     |the app — served by GitHub Pages, never regenerated       |
|`data/galley-data.json`          |the single source of truth (refreshed weekly by pipeline) |
|`schema/galley.schema.json`      |JSON Schema the data must satisfy                         |
|`scripts/generate.py`            |refresh + validate + publish (the only thing on a cadence)|
|`.github/workflows/refresh.yml`  |weekly scheduler + bot PR + auto-merge                    |
|`.github/workflows/ci.yml`       |lint + validate on every PR (required to merge)           |
|`k8s/cronjob.yml` + `Dockerfile` |cluster alternative (image name TBD — see issue #2)       |
|`pyproject.toml`                 |dependencies (`anthropic`, `jsonschema`); managed by uv   |

## Run it locally

```bash
uv run python scripts/generate.py --check                          # validate current file, no API call
ANTHROPIC_API_KEY=... uv run python scripts/generate.py --dry-run  # call API + validate, don't write
ANTHROPIC_API_KEY=... uv run python scripts/generate.py            # full refresh (atomic, validated)
```

```bash
python3 -m http.server 8000   # serve the app at http://localhost:8000/
```

## GitHub Actions setup

Two secrets required (**Settings → Secrets and variables → Actions**):

| Secret | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API — required for the refresh workflow |
| `GALLEY_PUSH_TOKEN` | Fine-grained PAT (Contents + Pull requests R/W, this repo only) — opens the bot PR so CI triggers correctly |

One repo setting: **Settings → General → Pull Requests → Allow auto-merge** (checkbox).

The refresh workflow runs every Sunday 14:00 UTC. Trigger a manual run anytime from
the **Actions** tab → `refresh-galley-data` → **Run workflow**.

## Option B — Kubernetes CronJob

See `k8s/cronjob.yml` and `Dockerfile`. Image name placeholder (`ghcr.io/YOU`) needs
updating — tracked as issue #2. The k8s path is not required for the GitHub Pages setup.

## Hosting

The app is a single `index.html` served by GitHub Pages from the root of `main`.
On load it fetches `data/galley-data.json` with `cache: 'no-store'`, so the weekly
pipeline refresh is always picked up without a hard reload. State (checked items,
theme, rotation mode) persists in `localStorage`.

## Honest caveats

- **Web search must be enabled** for your org in the Anthropic Console, and it bills
  separately (about $10 per 1,000 searches) on top of tokens. The generator runs up to
  20 searches/run in practice.
- **Model names move.** `GALLEY_MODEL` defaults to `claude-sonnet-4-6`; check
  <https://docs.anthropic.com/en/docs/about-claude/models> for current strings.
- The schema is a guardrail, not a nutritionist — it bounds calories/protein and
  structure, but you should still **eyeball labels** for GF + dairy-free before buying,
  since formulations change between refreshes.
- The generator **only writes on a clean validation**; a malformed or off-constraint
  generation is rejected and the last good file stays live.
- Each run costs roughly **$0.30–$0.35** (~$15–18/year at weekly cadence).
