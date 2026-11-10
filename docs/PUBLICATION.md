# Automated publication: operations and limitations

## What is implemented

- Six-hour GitHub Actions watcher for tagged `f1db/f1db` releases; manual force dispatch.
- Checksummed SQLite ingestion, integrity validation and bounded ZIP extraction.
- Full historical two-chain sequential NUTS fits, not ADVI. Fit diagnostics include driver/team latent effects as well as scale and career parameters.
- Separate strictly-before-race fits and joint rank simulations for held-out comparisons. Shared uncertainty is preserved, including unseen constructor-season draws.
- Structured OpenF1 lap, stint, pit, weather, race-control, driver, position and radio-link ingestion, plus a derived lap-by-lap top-ten timeline. Position snapshots can lag and do not establish on-track overtakes. No high-frequency bulk telemetry, journalism scraping or audio transcription in this first release.
- Hosted OpenRouter synthesis with a fixed prompt and bounded context/output. Every driver must be covered with known source IDs. All numbers appear in deterministic tables/charts, not LLM-generated prose.
- Failed diagnostics or editorial validation prevent the publication commit. Existing public artifacts are left unchanged until a complete release is ready.
- Static Vite frontend with Chart.js, local SQLite/WASM search/filter/sort/pagination, CSV downloads and accessible chart data tables. Existing Go application remains available and unchanged.

## Activate the watcher

The workflow is `.github/workflows/publication.yml`. Scheduled runs require it on the default branch and GitHub Actions enabled. GitHub may disable scheduled workflows in inactive public repositories; monitor this. Six-hour polling is intentional: this watches database releases, not live races.

In repository Settings → Secrets and variables → Actions:

1. Secret `OPENROUTER_API_KEY`: an API credential authorised for this task.
2. Variable `F1METRIX_LLM_MODEL`: an OpenRouter model identifier with JSON-output support and enough context/output capacity. No model is silently selected for spending.
3. Optional secret `VERCEL_DEPLOY_HOOK`: a Vercel deploy-hook URL if the Git integration does not trigger publication deploys as desired. Treat the hook as a credential.

Missing credentials fail before installing fitting dependencies or performing inference. There is no fabricated fallback article. Set an account-side LLM spending limit; network retries can result in duplicate billable requests after an ambiguous failure.

The workflow checks for a changed F1DB tag cheaply. Heavy jobs run on GitHub-hosted Ubuntu with single-threaded BLAS, two sequential NUTS chains, 1,500 tuning and 1,500 retained draws per chain. The job has a 330-minute total budget and each fit an 8,500-second budget. These are safety limits, not a promise that this model converges within them. Benchmark and choose a larger runner if needed. Do not weaken diagnostics to force publication.

No fitting has been run on the Raspberry Pi. No new fitting service has been installed on the shared Bookworm VPS. If moving the worker there, use the isolated resource-limited service example below, not a public-PR self-hosted runner.

## Deploy the frontend to Vercel

Import `PAndreew/f1metrix_streamlit` with repository root as the project root. `vercel.json` selects Vite, `npm run build:site`, and `site/dist`. Keep development dependencies available at build time. The exporter requires Python 3 with standard-library SQLite in the build environment; verify this in the Vercel build log.

The frontend is static: no Vercel database, API key, function, cron or model execution is required. It uses hash routes for this first version. This keeps deployment simple, but per-article SSR/SEO/RSS is a future enhancement—not implemented here.

At build time, `scripts/export_publication.py` selects `publication/model.json` if present; otherwise it builds an explicitly warned legacy preview from `data/bootstrap.json`. It exports a compact summary database and copies the SQLite WASM runtime. It does not ship the source F1DB database or posterior chains.

Publication source JSON lives in `publication/` and is committed by the bot only after all checks/builds pass. Each Vercel deployment bundles a complete consistent snapshot. Roll back a deployment or revert a publication commit to recover the previous version.

## Local development

```sh
npm ci --include=dev
npm run dev:site
# Vite prints the local URL.
npm run build:site
npm run preview:site
```

Legacy commands are preserved: `npm run build`, `npm run typecheck`, `go test ./...`.

## Worker execution

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r model/requirements.txt pytest
python -m pytest tests
python -m pipeline.run --check
# Configure OPENROUTER_API_KEY and F1METRIX_LLM_MODEL securely first:
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pipeline.run
```

The worker uses a Linux file lock and a `.pipeline/` scratch/archive directory, which is ignored by Git. It never serves that directory. Successful runs retain posterior NetCDFs, model summaries, forecasts and evidence packages there for audit. Source archive checksum and release are recorded. Keep these artifacts in durable storage if you need a permanent audit trail; CI diagnostic artifacts expire. Clean up retained worker archives under an explicit retention policy.

A cold start analyses only the latest completed race. Normal updates process races after the last publication date. A new release with no new race reanalyses the latest event, covering amended latest classification. **Automatic historical correction fan-out and arbitrary backfill are not implemented**; old articles can remain tied to their original source release. Expose this limitation rather than silently treating all history as corrected.

The post-event historical fit is made first and supplied to the writer together with the held-out forecast. If several events are being caught up, that updated model includes all currently released outcomes; it is not an event-time posterior for each older event. Every event's held-out forecast still excludes its target race and later results.

## Statistical interpretation

The historical model is an outcome model over normal-order classification scores. It is not a causal driver-skill experiment or lap-time model. Forecasts here are retrospectively reconstructed, conditional on avoiding technical retirements; entrant identities come from the target race entry/result list. They must not be represented as frozen live forecasts.

Simulation draws rank all entrants jointly. A driver's expected place is a distribution summary, not a promise; `placesAboveExpectation` is an outcome contrast, not a driver rating. Incident fault is not inferred from retirement categories. The underlying preprocessing still groups some collision outcomes as driver-related; evaluate that sensitivity before making substantive talent claims.

Sampler gates: maximum R-hat at most 1.01, minimum bulk ESS at least 400, zero divergences, two chains. Approximate and legacy diagnostics fail closed. Passing these checks is not equivalent to predictive calibration. Rolling-origin calibration, held-out baseline comparisons, tail ESS requirements, retirement-policy sensitivity and a reliability model remain scientific follow-up work.

The public lap-median metric excludes starts, pit laps and conservatively buffered neutralisations. It is not corrected for compound/age, traffic, deleted laps, fuel or damage; it must not be used to rank underlying driver ability. The system prompt says so. The writer has no executable tools, chart-code generation or deployment credentials.

Editorial validation enforces schema, coverage, citations and no generated numeric literals/HTML/URLs. It cannot mechanically prove all qualitative claims true or detect every spelled-out quantity. Full semantic fact verification and independent editorial review remain limitations of automatic publication. Source IDs and schema compliance are not proofs that a citation entails a claim. Articles are labelled provisional and AI-generated.

## Resource-limited VPS option

`ops/f1metrix-publication.service` and `.timer` are optional templates, not installed services. Use a dedicated unprivileged account, a dedicated checkout/venv, and root-owned environment file. On the inspected two-core/four-GB VPS start at one CPU and 1.5 GiB RAM; a full fit may exceed this and must fail safely. Do not point it at Bookworm directories or volumes. The template runs the pipeline only; publication commits/deployments need a separately authorised trusted deployment step.

## Licensing and data rights

Repository code is MIT licensed. Dependencies retain their licences. This does not grant rights to third-party timing feeds, commentary, F1 branding or radio audio. Follow upstream access and usage terms. This pipeline fetches public structured endpoints, links sources, and does not ingest copyrighted journalism or reproduce radio audio. F1DB and upstream data require their own attribution/rights review for your deployment.
