# F1 Metrix

Interactive Bayesian Formula One rankings. A small Go server renders filters, tables, articles and Chart.js visualizations; a separate PyMC batch job downloads F1DB and atomically publishes a JSON snapshot.

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
