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
|`data/galley-data.json`          |the single source of truth (seeded from the live app)     |
|`schema/galley.schema.json`      |JSON Schema the data must satisfy                         |
|`scripts/generate.py`            |refresh + validate + publish (the only thing on a cadence)|
|`.github/workflows/refresh.yml`  |**recommended** scheduler — zero infra                    |
|`k8s/cronjob.yaml` + `Dockerfile`|cluster alternative, if you prefer                        |
|`requirements.txt`               |`anthropic`, `jsonschema`                                 |

## Run it locally

```bash
cd galley-pipeline
pip install -r requirements.txt
python scripts/generate.py --check      # validate the current file, no API call
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/generate.py --dry-run    # call the API + validate, but don't write
python scripts/generate.py              # refresh for real (atomic, validated)
```

## Option A — GitHub Actions (recommended)

1. Push this folder to a repo.
1. **Settings → Secrets and variables → Actions** → add `ANTHROPIC_API_KEY`.
1. The workflow runs every Sunday and commits the refreshed JSON. Trigger a test run
   from the **Actions** tab (“Run workflow”).
1. Serve the app + JSON from GitHub Pages (or any static host).

## Option B — Kubernetes CronJob

```bash
kubectl create secret generic galley-secrets --from-literal=ANTHROPIC_API_KEY=sk-ant-...
docker build -t ghcr.io/YOU/galley-pipeline:latest .   # uses the included Dockerfile
docker push ghcr.io/YOU/galley-pipeline:latest
kubectl apply -f k8s/cronjob.yaml
```

The job writes to a PVC; point an nginx static sidecar at that volume, or change the
container command to `aws s3 cp /data/galley-data.json s3://your-bucket/` to publish.

## The one app-shell change (to consume the JSON when hosted)

Right now the app keeps its data inline and persists checkboxes via Claude’s artifact
storage. To run as a normal hosted site that reads the refreshed file, make two edits
to `the-galley.html`:

**1. Load data from the JSON instead of the inline `const` blocks.** Replace the
`CATALOG / MEALS / BATCH / ROTATION / PLAN / SHOP / DAYS / CAL_*` declarations with a
fetch, and wrap `init()` so it runs after load:

```js
let CATALOG, MEALS, BATCH, ROTATION, PLAN, SHOP, DAYS, CAL_LO, CAL_HI, P_LO, P_HI;
async function loadData(){
  const d = await (await fetch('galley-data.json', {cache:'no-store'})).json();
  ({catalog:CATALOG, meals:MEALS, batch:BATCH, rotation:ROTATION, plan:PLAN, shop:SHOP, days:DAYS} = d);
  ({calLo:CAL_LO, calHi:CAL_HI, pLo:P_LO, pHi:P_HI} = d.targets);
}
// then: loadData().then(init);
```

**2. Swap persistence off Claude storage to `localStorage`** (the app calls go
through the `sget`/`sset` helpers, so this is the whole change):

```js
async function sget(k){ return localStorage.getItem('galley:'+k); }
async function sset(k,v){ localStorage.setItem('galley:'+k, v); }
```

That’s it — everything else (themes, tabs, checks, copy buttons) keeps working.

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