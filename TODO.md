# TODO

Tracked as GitHub issues on [jpearsall/the-galley](https://github.com/jpearsall/the-galley).

## Open (k8s path — deferred, not needed for GitHub Pages setup)

- [ ] **#2** Replace `ghcr.io/YOU` placeholder in `k8s/cronjob.yml` and README with the real image name
- [ ] **#4** Add GitHub Actions workflow to build and push the Docker image to GHCR on push to `main`

## Closed

- [x] **#1** Fix README — replace pip/requirements.txt references with uv, fix `k8s/cronjob.yaml` → `k8s/cronjob.yml`, remove deleted `requirements.txt` row from files table
- [x] **#3** Fix Python version mismatch — `.python-version` and `pyproject.toml` require 3.14 but Dockerfile builds on `python3.12-bookworm-slim`; align them
- [x] **#5** Wire up the app shell — fetch from `data/galley-data.json`, swap `sget`/`sset` to `localStorage`, rename to `index.html`
- [x] **#6** Enable GitHub Pages — Settings → Pages → Deploy from branch → `main` / `/ (root)`
- [x] **#7** Fix `$id` in `schema/galley.schema.json` — replace `https://example.com/` with the real hosted URL
