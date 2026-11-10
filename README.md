# F1 Metrix

An open-source Formula One analytics journal: historical PyMC estimates, held-out race simulations, evidence-grounded AI writing, and a responsive, static Vercel frontend.

## New publication frontend and pipeline

```sh
npm ci --include=dev
npm run dev:site
npm run build:site
python -m pipeline.run --check
```

Import this repository into Vercel; `vercel.json` configures the static build. The site has Chart.js uncertainty charts, searchable/filterable/sortable browser-local SQLite tables, CSV export, article views and a methodology page. Until a validated release exists, it clearly labels its bundled historical data as an unreliable legacy preview.

A six-hour GitHub Actions watcher checks F1DB releases. On change it verifies and downloads SQLite, runs full NUTS fits, reconstructs held-out joint race outcomes, fetches structured OpenF1 evidence, requests a source-linked article, validates the output and commits the completed publication. The previous publication remains live on failure.

**Activation requires** repository secret `OPENROUTER_API_KEY` and Actions variable `F1METRIX_LLM_MODEL`. No LLM credential or Vercel project is preconfigured. Full sampling is deliberately not run on the Raspberry Pi. See **[publication operations, limits and deployment](docs/PUBLICATION.md)** before enabling heavy jobs. Passing sampler checks does not replace predictive calibration, and this first release does not transcribe radio or scrape journalism.

The original lightweight Go site and its deployment remain intact below.

## Architecture

- `model/data.py` — auditable F1DB preprocessing and retirement policy
- `model/fit.py` — cross-classified PyMC model and snapshot export
- `scripts/update_model.py` — release check, SHA-256 verification, fit, atomic publish
- `cmd/f1metrix` / `internal/site` — read-only Go web server
- `web/static/app.ts` — minimal TypeScript chart code
- `posts/*.md` — owner-authored articles
- `docs/MODEL_REVIEW.md` — review of the inherited fit and research basis

The model and web process are deliberately separated. A failed fit never replaces the last good snapshot, and the Go process notices a successful atomic replacement without restarting.

## Local website

```sh
npm ci
npm run build
go run ./cmd/f1metrix
# http://localhost:8080
```

Until v2 has run, the site uses `data/bootstrap.json`, generated from the inherited database and visibly marked provisional.

## Run the model

A full reproducible refresh downloads and verifies the latest F1DB release:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r model/requirements.txt
python scripts/update_model.py --method advi
```

For publishable inference, use NUTS rather than mean-field ADVI:

```sh
python scripts/update_model.py --method nuts --force
```

NUTS defaults to two sequential chains to stay within a small server's memory. Inspect the diagnostics and posterior predictive behavior before presenting a fit as converged.

## Tests

```sh
go test ./...
python -m pytest tests
npm run typecheck
```

## Add a post

Add `posts/YYYY-MM-DD-slug.md`, beginning with a Markdown heading, commit it, and deploy. Posts are trusted owner content; there is intentionally no public CMS or admin attack surface.

## Production

```sh
./scripts/deploy-vps.sh
```

The production setup:

- joins the same external Caddy network used by Potpuri;
- serves `f1metrix.46-62-236-54.sslip.io` with automatic HTTPS;
- stores model data in a dedicated Docker volume;
- checks F1DB every day at 04:17 via `/etc/cron.d/f1metrix`;
- uses `flock` to prevent overlapping fits;
- reruns only when F1DB publishes a new release tag;
- keeps serving the previous snapshot if download, checksum, inference or export fails.

Useful commands:

```sh
# Follow updater output
ssh root@46.62.236.54 tail -f /var/log/f1metrix-model.log

# Force a refresh
ssh root@46.62.236.54 'cd /opt/f1metrix && docker compose --profile model -f compose.production.yml run --rm model --force'

# Inspect web logs
ssh root@46.62.236.54 docker logs f1metrix-web --tail 100
```
