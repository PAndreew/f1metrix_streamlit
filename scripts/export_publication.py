#!/usr/bin/env python3
"""Build browser-safe artifacts using stdlib SQLite. Never ships posterior/raw source DB."""
import json
from pathlib import Path
import shutil
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.common import require_fit


def export():
    source = ROOT / 'publication/model.json'
    validated = source.exists()
    model = json.loads((source if validated else ROOT / 'data/bootstrap.json').read_text())
    if validated:
        require_fit(model)
    public = ROOT / 'site/public/data'
    public.mkdir(parents=True, exist_ok=True)
    articles = []
    for p in sorted((ROOT / 'publication/articles').glob('*.json')):
        article = json.loads(p.read_text())
        # Radio URLs and full evidence timeline are not necessary for rendering.
        articles.append(article)
    articles.sort(key=lambda a: a['date'], reverse=True)
    payload = {'model': model, 'articles': articles, 'validated': validated,
               'notice': '' if validated else 'Historical preview only · August 2026 legacy fit · not converged. These are not current, validated rankings.'}
    (public / 'publication.json').write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False))
    path = public / 'rankings.sqlite'
    path.unlink(missing_ok=True)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE drivers (id TEXT PRIMARY KEY, name TEXT, nationality TEXT, races INTEGER, first_year INTEGER, last_year INTEGER, skill REAL, low REAL, high REAL, rank INTEGER)')
        db.executemany('INSERT INTO drivers VALUES (?,?,?,?,?,?,?,?,?,?)', [(d['id'],d['name'],d['nationality'],d['races'],d['firstYear'],d['lastYear'],d['skill'],d['low'],d['high'],d['rank']) for d in model['drivers']])
        db.execute('CREATE TABLE metadata (key TEXT PRIMARY KEY,value TEXT)')
        db.executemany('INSERT INTO metadata VALUES (?,?)', [('model',model['metadata']['model']),('validated',str(validated).lower())])
    wasm = ROOT / 'node_modules/sql.js/dist/sql-wasm.wasm'
    if wasm.exists():
        shutil.copyfile(wasm, ROOT / 'site/public/sql-wasm.wasm')
    print(f'Exported {len(model["drivers"])} driver rows, {len(articles)} articles; validated={validated}')


if __name__ == '__main__':
    export()
