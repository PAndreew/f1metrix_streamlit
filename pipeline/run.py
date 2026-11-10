"""Release watcher and transactional publication pipeline.
Run: python -m pipeline.run [--check | --force]
Heavy computation intentionally runs outside Vercel and outside the Raspberry Pi.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
import shutil
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from .common import atomic_json, digest, fetch, latest_release, require_fit
from .editorial import generate
from .evidence import collect

ROOT = Path(__file__).resolve().parents[1]


def source_database(release, work):
    assets = {a['name']: a['browser_download_url'] for a in release['assets']}
    raw = fetch(assets['f1db-sqlite.zip'])
    checksums = fetch(assets['checksums_sha256.txt']).decode()
    expected = next(line.split()[0] for line in checksums.splitlines() if line.split()[-1].lstrip('*') == 'f1db-sqlite.zip')
    if digest(raw) != expected:
        raise ValueError('F1DB archive checksum mismatch')
    archive = work / 'source.zip'
    archive.write_bytes(raw)
    with zipfile.ZipFile(archive) as z:
        members = [m for m in z.infolist() if m.filename.endswith('.db')]
        if len(members) != 1 or members[0].file_size > 512 * 1024 * 1024:
            raise ValueError('Unexpected SQLite archive layout/size')
        database = work / 'f1db.db'
        # Copy the bytes, never extract attacker-controlled paths.
        with z.open(members[0]) as src, database.open('wb') as dst:
            while chunk := src.read(1024 * 1024):
                dst.write(chunk)
    with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as db:
        if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity check failed')
        db.execute('SELECT race_id, driver_id, position_display_order FROM race_result LIMIT 1')
    return database, expected


def races_to_process(database, state):
    with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        races = [dict(r) for r in db.execute('''SELECT r.id,r.date,r.year,r.round,r.official_name
            FROM race r WHERE r.date <= date('now') AND EXISTS
            (SELECT 1 FROM race_result rr WHERE rr.race_id=r.id)
            ORDER BY r.date,r.round''')]
    if not races:
        raise ValueError('No completed races')
    # Cold start publishes latest only; normal updates process new events plus latest
    # (which also catches amended latest classification). Historical corrections can
    # be explicitly replayed in a future backfill; never refit every event each poll.
    if not state:
        return races[-1:]
    cutoff = state.get('lastRaceDate', '')
    return [r for r in races if r['date'] > cutoff] or races[-1:]


def fit(database, work, tag, race=None):
    name = f"before-{race['id']}" if race else 'updated'
    output = work / f'{name}.json'
    command = [sys.executable, str(ROOT / 'model/fit.py'), '--database', str(database), '--output', str(output),
        '--artifact', str(work / f'{name}.nc'), '--release', tag, '--method', 'nuts',
        '--draws', os.getenv('F1METRIX_DRAWS', '1500'), '--tune', os.getenv('F1METRIX_TUNE', '1500')]
    if race:
        command += ['--before-date', race['date'], '--forecast-race', str(race['id']), '--forecast-output', str(work / f"forecast-{race['id']}.json")]
    subprocess.run(command, cwd=ROOT, check=True, timeout=int(os.getenv('F1METRIX_FIT_TIMEOUT', '14400')))
    snapshot = json.loads(output.read_text())
    require_fit(snapshot)
    return snapshot


def evaluation(database, race, forecast):
    with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        results = [dict(r) for r in db.execute('''SELECT rr.driver_id AS driverId, rr.position_display_order AS position,
            rr.reason_retired AS retirementReason, rr.constructor_id AS constructorId,
            d.first_name || ' ' || d.last_name AS name FROM race_result rr JOIN driver d ON d.id=rr.driver_id
            WHERE rr.race_id=? ORDER BY rr.position_display_order''', (race['id'],))]
    pred = {r['driver_id']: r for r in forecast['drivers']}
    for r in results:
        f = pred[r['driverId']]
        r.update(expectedPosition=f['expectedPosition'], low=f['low'], high=f['high'], distribution=f['distribution'],
                 placesAboveExpectation=round(f['expectedPosition'] - r['position'], 3))
        # Discrete lower-tail percentile, NOT a p-value or talent probability.
        r['probabilityAtLeastAsGood'] = round(sum(f['distribution'][:r['position']]), 6)
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check', action='store_true')
    p.add_argument('--force', action='store_true')
    p.add_argument('--work-dir', type=Path, default=ROOT / '.pipeline')
    a = p.parse_args()
    a.work_dir.mkdir(parents=True, exist_ok=True)
    with (a.work_dir / 'lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        release = latest_release()
        public = ROOT / 'publication'
        state_file = public / 'state.json'
        state = json.loads(state_file.read_text()) if state_file.exists() else {}
        changed = state.get('tag') != release['tag_name']
        print(json.dumps({'tag': release['tag_name'], 'changed': changed}))
        if a.check or not changed and not a.force:
            return
        # Fail before expensive fitting if article credentials are absent.
        if not os.getenv('OPENROUTER_API_KEY') or not os.getenv('F1METRIX_LLM_MODEL'):
            raise RuntimeError('Configure OpenRouter API secret and model variable before running publication')
        with tempfile.TemporaryDirectory(dir=a.work_dir) as temp:
            work = Path(temp)
            database, sha = source_database(release, work)
            races = races_to_process(database, state)
            updated = fit(database, work, release['tag_name'])
            articles = []
            for race in races:
                before = fit(database, work, release['tag_name'], race)
                forecast = json.loads((work / f"forecast-{race['id']}.json").read_text())
                rows = evaluation(database, race, forecast)
                evidence = collect(race, rows, work / f"evidence-{race['id']}")
                package = {'race': race, 'forecast': forecast, 'evaluations': rows, 'evidence': evidence,
                    'sources': [{'id': 'f1db', 'url': release['html_url'], 'sha256': sha}, *evidence['sources']],
                    'diagnostics': before['metadata']['diagnostics'],
                    'updatedModel': {'metadata': updated['metadata'], 'drivers': [d for d in updated['drivers'] if d['id'] in {r['driverId'] for r in rows}]}}
                article = generate(package)
                article.update(id=str(race['id']), date=race['date'], race=race, forecast=forecast,
                    evaluations=rows, evidence=evidence, sources=package['sources'],
                    status='provisional', generatedAt=datetime.now(timezone.utc).isoformat())
                atomic_json(work / f"package-{race['id']}.json", package)
                articles.append(article)
            # Git commits/deployments expose the complete publication atomically. The worker's
            # local directory is never served. State is written last so failures retry safely.
            # Preserve auditable fit/evidence artifacts before the temporary workspace disappears.
            archive = a.work_dir / 'archive' / (release['tag_name'].replace('/', '_') + '-' + sha[:12])
            archive.mkdir(parents=True, exist_ok=True)
            for path in work.iterdir():
                if path.is_file() and path.suffix in ('.json', '.nc'):
                    shutil.copy2(path, archive / path.name)
                elif path.is_dir() and path.name.startswith('evidence-'):
                    shutil.copytree(path, archive / path.name, dirs_exist_ok=True)
            public.mkdir(exist_ok=True)
            atomic_json(public / 'model.json', updated)
            for article in articles:
                atomic_json(public / 'articles' / f"{article['id']}.json", article)
            ids = sorted(set(state.get('raceIds', []) + [str(r['id']) for r in races]))
            atomic_json(state_file, {'tag': release['tag_name'], 'sha256': sha, 'lastRaceDate': races[-1]['date'], 'raceIds': ids})
            # Full posterior/source retained privately on worker. CI uploads compact provenance only.
            atomic_json(a.work_dir / 'last-run.json', {'source': release['html_url'], 'sha256': sha,
                'diagnostics': updated['metadata']['diagnostics'], 'raceIds': ids})


if __name__ == '__main__':
    main()
