import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import zipfile

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'model'))
from pipeline.common import require_fit, digest, atomic_json
from pipeline.editorial import validate
from pipeline import run
from forecast import rank_scores


def test_fit_gate_accepts_only_good_diagnostics():
    require_fit({'metadata': {'diagnostics': {'maxRhat': 1.005, 'minEssBulk': 500, 'divergences': 0}}})


@pytest.mark.parametrize('diagnostics', [
    {}, {'warning': 'legacy'}, {'maxRhat': 1.1, 'minEssBulk': 500, 'divergences': 0},
    {'maxRhat': 1.0, 'minEssBulk': 399, 'divergences': 0},
    {'maxRhat': 1.0, 'minEssBulk': 500, 'divergences': 1},
    {'maxRhat': float('nan'), 'minEssBulk': 500, 'divergences': 0},
])
def test_fit_gate_fails_closed(diagnostics):
    with pytest.raises(ValueError):
        require_fit({'metadata': {'diagnostics': diagnostics}})


def package():
    return {'sources': [{'id': 'laps'}, {'id': 'f1db'}], 'evaluations': [{'driverId': 'a'}, {'driverId': 'b'}]}


def article():
    return {'title': 'A controlled drive', 'summary': 'An uncertain comparison.',
            'sections': [{'heading': 'The result', 'text': 'A strong outcome.', 'sources': ['f1db']},
                         {'heading': 'The evidence', 'text': 'Context matters.', 'sources': ['laps']}],
            'drivers': [{'driverId': 'a', 'assessment': 'Strong execution.', 'sources': ['laps']},
                        {'driverId': 'b', 'assessment': 'Insufficient evidence.', 'sources': ['f1db']}]}


def test_editorial_accepts_supported_structure():
    validate(article(), package())


@pytest.mark.parametrize('bad', ['Won by 12 seconds', '<script>bad</script>', 'See https://evil.test'])
def test_editorial_rejects_unverified_numbers_and_markup(bad):
    a = article()
    a['summary'] = bad
    with pytest.raises(ValueError):
        validate(a, package())


def test_editorial_requires_every_driver_once():
    a = article()
    a['drivers'][1]['driverId'] = 'a'
    with pytest.raises(ValueError):
        validate(a, package())


def test_editorial_rejects_unknown_citation():
    a = article()
    a['sections'][0]['sources'] = ['invented']
    with pytest.raises(ValueError):
        validate(a, package())


def test_joint_simulation_has_exactly_one_of_each_position():
    ranks = rank_scores(np.random.default_rng(3).normal(size=(500, 22)))
    assert np.all(np.sort(ranks, axis=1) == np.arange(1, 23))
    assert np.all(ranks.sum(axis=1) == 253)


def test_lap_snapshots_use_only_updates_known_at_lap_start():
    from pipeline.evidence import lap_snapshots
    laps = [{'lap_number': 1, 'date_start': '2026-01-01T12:00:00+00:00'},
            {'lap_number': 2, 'date_start': '2026-01-01T12:01:40+00:00'}]
    positions = [{'driver_number': 1, 'position': 1, 'date': '2026-01-01T11:59:59+00:00'},
                 {'driver_number': 2, 'position': 2, 'date': '2026-01-01T11:59:59+00:00'},
                 {'driver_number': 2, 'position': 1, 'date': '2026-01-01T12:01:00+00:00'},
                 {'driver_number': 1, 'position': 2, 'date': '2026-01-01T12:01:00+00:00'},
                 {'driver_number': 1, 'position': 1, 'date': '2026-01-01T12:02:00+00:00'}]
    result = lap_snapshots(laps, positions, {1:'A',2:'B'})
    assert result[0]['reportedTopTen'][0]['name'] == 'A'
    assert result[1]['reportedTopTen'][0]['name'] == 'B'


def test_atomic_json_rejects_nan(tmp_path):
    with pytest.raises(ValueError):
        atomic_json(tmp_path / 'bad.json', {'x': float('nan')})
    assert not (tmp_path / 'bad.json').exists()


def test_source_checksum_mismatch_prevents_sqlite_use(monkeypatch, tmp_path):
    release = {'assets': [{'name': 'f1db-sqlite.zip', 'browser_download_url': 'archive'},
                         {'name': 'checksums_sha256.txt', 'browser_download_url': 'checksums'}]}
    monkeypatch.setattr(run, 'fetch', lambda url: b'bad' if url == 'archive' else b'0000  f1db-sqlite.zip')
    with pytest.raises(ValueError, match='checksum'):
        run.source_database(release, tmp_path)


def test_sqlite_member_path_cannot_escape_work_directory(monkeypatch, tmp_path):
    dbfile = tmp_path / 'source.db'
    with sqlite3.connect(dbfile) as db:
        db.execute('CREATE TABLE race_result(race_id,driver_id,position_display_order)')
    content = io.BytesIO()
    with zipfile.ZipFile(content, 'w') as archive:
        archive.writestr('../../outside.db', dbfile.read_bytes())
    raw = content.getvalue()
    release = {'assets': [{'name': 'f1db-sqlite.zip', 'browser_download_url': 'archive'},
                         {'name': 'checksums_sha256.txt', 'browser_download_url': 'checksums'}]}
    monkeypatch.setattr(run, 'fetch', lambda url: raw if url == 'archive' else (digest(raw)+'  f1db-sqlite.zip').encode())
    result, _ = run.source_database(release, tmp_path)
    assert result == tmp_path / 'f1db.db'
    assert not (tmp_path.parent / 'outside.db').exists()


def test_cold_start_processes_only_latest_race(tmp_path):
    path = tmp_path / 'data.db'
    with sqlite3.connect(path) as db:
        db.executescript('''CREATE TABLE race(id,date,year,round,official_name);
        CREATE TABLE race_result(race_id);
        INSERT INTO race VALUES (1,'2020-01-01',2020,1,'First'),(2,'2020-02-01',2020,2,'Second');
        INSERT INTO race_result VALUES (1),(2);''')
    assert [r['id'] for r in run.races_to_process(path, {})] == [2]


def test_forecast_export_matches_entrants_and_probability_mass(monkeypatch, tmp_path):
    import forecast
    import pandas as pd
    from types import SimpleNamespace
    path = tmp_path / 'data.db'
    with sqlite3.connect(path) as db:
        db.executescript('''CREATE TABLE race(id,date,year,official_name);
        CREATE TABLE driver(id,date_of_birth,first_name,last_name);
        CREATE TABLE race_result(race_id,driver_id,constructor_id);
        INSERT INTO race VALUES (7,'2020-02-01',2020,'Target');
        INSERT INTO driver VALUES ('a','1990-01-01','Driver','A'),('b','1991-01-01','Driver','B');
        INSERT INTO race_result VALUES (7,'a','new-team'),(7,'b','new-team');''')
    values = {'driver_skill': np.zeros((50,2)), 'constructor_skill': np.zeros((50,1)),
              'constructor_year_skill': np.zeros((50,1)), 'experience_steps': np.zeros((50,4))}
    monkeypatch.setattr(forecast, 'posterior_matrix', lambda _, k: values.get(k, np.ones(50)))
    data = SimpleNamespace(driver_ids=['a','b'],constructor_ids=['old-team'],constructor_year_ids=['old-team:2019'],
                           observations=pd.DataFrame({'driver_id':['a','b'],'year':[2019,2019]}))
    output = tmp_path / 'forecast.json'
    forecast.simulate(data, None, path, 7, '2020-02-01', output)
    result = json.loads(output.read_text())
    assert result['kind'] == 'retrospective-held-out'
    assert result['simulations'] == 500
    assert len(result['drivers']) == 2
    for row in result['drivers']:
        assert sum(row['distribution']) == pytest.approx(1, abs=1e-5)
    assert sum(row['expectedPosition'] for row in result['drivers']) == pytest.approx(3, abs=.002)
    with pytest.raises(ValueError, match='cutoff'):
        forecast.simulate(data, None, path, 7, '2020-01-01', output)


def test_heldout_cutoff_excludes_target_race(tmp_path):
    from data import load_model_data
    path = tmp_path / 'data.db'
    with sqlite3.connect(path) as db:
        db.executescript('''CREATE TABLE race(id,year,round,date,official_name,grand_prix_id,circuit_type);
        CREATE TABLE driver(id,first_name,last_name,name,nationality_country_id,date_of_birth);
        CREATE TABLE constructor(id,name,full_name,country_id);
        CREATE TABLE race_result(race_id,position_display_order,driver_id,constructor_id,grid_position_number,reason_retired,laps,shared_car);
        INSERT INTO driver VALUES ('a','Driver','One','Driver One','GB','1990-01-01');
        INSERT INTO constructor VALUES ('team','Team','Team','GB');
        INSERT INTO race VALUES(1,2020,1,'2020-01-01','Prior','a','RACE'),(2,2020,2,'2020-02-01','Target','b','RACE');
        INSERT INTO race_result VALUES(1,1,'a','team',1,NULL,50,0),(2,1,'a','team',1,NULL,50,0);''')
    data = load_model_data(path, before_date='2020-02-01')
    assert data.observations.race_id.tolist() == [1]
