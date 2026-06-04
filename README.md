# The Galley — auto-refresh pipeline

Keeps the app’s **data** current on a weekly cadence without ever regenerating the
app itself. The app shell (HTML/JS) is fixed; only `data/galley-data.json` changes.

```
  ┌─ cron (Sun 14:00 UTC) ─┐
  │  GitHub Actions  OR     │
  │  k8s CronJob            │
  └───────────┬─────────────┘
              ▼
      scripts/generate.py
       ├─ calls Claude API (web_search) to re-verify products & refresh picks
       ├─ validates output against schema/galley.schema.json
       ├─ checks referential integrity (every id used actually exists)
       └─ publishes data/galley-data.json  ONLY if valid  (else keeps last good)
              ▼
      static host serves galley-data.json  →  the app fetches it on load
```

Why it’s built this way: LLM-generated *markup* drifts and breaks. LLM-generated
*data*, validated against a strict schema, doesn’t — a bad generation is rejected
and the previous good file stays live. This is exactly why the app was refactored
to separate data from presentation.

## Files

|Path                             |Role                                                      |
|---------------------------------|----------------------------------------------------------|
|`index.html`                     |the app — served by GitHub Pages, never regenerated       |
|`data/galley-data.json`          |the single source of truth (refreshed weekly by pipeline) |
|`schema/galley.schema.json`      |JSON Schema the data must satisfy                         |
|`scripts/generate.py`            |refresh + validate + publish (the only thing on a cadence)|
|`.github/workflows/refresh.yml`  |**recommended** scheduler — zero infra                    |
|`k8s/cronjob.yml` + `Dockerfile` |cluster alternative, if you prefer                        |
|`pyproject.toml`                 |dependencies (`anthropic`, `jsonschema`); managed by uv   |

## Run it locally

```bash
uv run python scripts/generate.py --check                        # validate the current file, no API call
ANTHROPIC_API_KEY=... uv run python scripts/generate.py --dry-run  # call the API + validate, but don't write
ANTHROPIC_API_KEY=... uv run python scripts/generate.py            # refresh for real (atomic, validated)
```

## Option A — GitHub Actions (recommended)

1. **Settings → Secrets and variables → Actions** → add `ANTHROPIC_API_KEY`.
1. The workflow runs every Sunday and commits the refreshed JSON. Trigger a test run
   from the **Actions** tab (“Run workflow”).
1. **Settings → Pages** → source: Deploy from branch → `main` / `/ (root)` → Save.

## Option B — Kubernetes CronJob

```bash
kubectl create secret generic galley-secrets --from-literal=ANTHROPIC_API_KEY=sk-ant-...
docker build -t ghcr.io/YOU/galley-pipeline:latest .   # uses the included Dockerfile
docker push ghcr.io/YOU/galley-pipeline:latest
kubectl apply -f k8s/cronjob.yaml
```

The job writes to a PVC; point an nginx static sidecar at that volume, or change the
container command to `aws s3 cp /data/galley-data.json s3://your-bucket/` to publish.

## Hosting

The app is a single `index.html` served by GitHub Pages from the root of `main`.
On load it fetches `data/galley-data.json` with `cache: ‘no-store’`, so the weekly
pipeline refresh is always picked up without a hard reload. State (checked items,
theme, rotation mode) persists in `localStorage`.

To run locally:

```bash
python3 -m http.server 8000
# open http://localhost:8000/
```

## Honest caveats

- **Web search must be enabled** for your org in the Anthropic Console, and it bills
  separately (about $10 per 1,000 searches) on top of tokens. The generator caps it at
  8 searches/run.
- **Model names move.** `GALLEY_MODEL` defaults to `claude-sonnet-4-6`; check
  <https://docs.claude.com/en/docs/about-claude/models> for current strings, or set Opus
  (`claude-opus-4-8`) if you want stronger research.
- The schema is a guardrail, not a nutritionist — it bounds calories/protein and
  structure, but you should still **eyeball labels** for GF + dairy-free before buying,
  since formulations change between refreshes.
- The generator **only writes on a clean validation**; a malformed or off-constraint
  generation is rejected and the last good file stays live.