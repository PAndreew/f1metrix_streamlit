"""Held-out, joint rank simulations. Conditional on no technical retirement.
No actual finishing positions, grid, or target-race lap data enter the scores.
Entrant selection is retrospective; this is not a claimed live forecast.
"""
from datetime import date
import json
import sqlite3
import numpy as np
from fit import posterior_matrix


def rank_scores(scores):
    order = np.argsort(-scores, axis=1)
    ranks = np.empty_like(order)
    np.put_along_axis(ranks, order, np.arange(1, scores.shape[1] + 1)[None, :], axis=1)
    return ranks


def simulate(data, idata, database, race_id, cutoff, output):
    with sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        race = dict(db.execute('SELECT id, date, year, official_name FROM race WHERE id=?', (race_id,)).fetchone())
        entrants = [dict(r) for r in db.execute('''SELECT rr.driver_id, rr.constructor_id, d.date_of_birth,
            d.first_name || ' ' || d.last_name AS name FROM race_result rr
            JOIN driver d ON d.id=rr.driver_id WHERE rr.race_id=? ORDER BY rr.driver_id''', (race_id,))]
    if race['date'] != cutoff:
        raise ValueError('Forecast cutoff must equal target race date')
    if len(entrants) < 2:
        raise ValueError('Incomplete entrant list')
    rng = np.random.default_rng(20261110)
    ds, cs, ys = [posterior_matrix(idata, k) for k in ['driver_skill', 'constructor_skill', 'constructor_year_skill']]
    count = ds.shape[0]
    scalar = lambda k: posterior_matrix(idata, k).reshape(count)
    exp = np.column_stack([np.zeros(count), np.cumsum(posterior_matrix(idata, 'experience_steps'), axis=1)])
    scores = []
    unseen_teams, unseen_seasons = {}, {}
    for e in entrants:
        # An unseen entrant/team receives a population draw, not a spurious zero-uncertainty estimate.
        driver = ds[:, data.driver_ids.index(e['driver_id'])] if e['driver_id'] in data.driver_ids else rng.normal(size=count) * scalar('sigma_driver')
        if e['constructor_id'] not in data.constructor_ids and e['constructor_id'] not in unseen_teams:
            unseen_teams[e['constructor_id']] = rng.normal(size=count) * scalar('sigma_constructor')
        team = cs[:, data.constructor_ids.index(e['constructor_id'])] if e['constructor_id'] in data.constructor_ids else unseen_teams[e['constructor_id']]
        key = f"{e['constructor_id']}:{race['year']}"
        if key not in data.constructor_year_ids and key not in unseen_seasons:
            unseen_seasons[key] = rng.normal(size=count) * scalar('sigma_constructor_year')
        season = ys[:, data.constructor_year_ids.index(key)] if key in data.constructor_year_ids else unseen_seasons[key]
        age = (date.fromisoformat(cutoff) - date.fromisoformat(e['date_of_birth'])).days / 365.2425
        prior = set(data.observations.loc[data.observations.driver_id == e['driver_id'], 'year'])
        experience = sum(race['year'] - offset in prior for offset in range(1, 5))
        mu = scalar('intercept') + driver + team + season - scalar('age_decline') * ((age - scalar('age_peak')) / 10) ** 2 + exp[:, experience]
        scores.append(mu)
    # Repeat uncertainty draws to reduce Monte Carlo noise, not to pretend there is more posterior ESS.
    mu = np.stack(scores, axis=1)
    mu = np.repeat(mu, 10, axis=0)
    noise = rng.standard_t(np.repeat(scalar('nu_minus_two') + 2, 10)[:, None], size=mu.shape)
    ranks = rank_scores(mu + noise * np.repeat(scalar('sigma'), 10)[:, None])
    rows = []
    for i, e in enumerate(entrants):
        r = ranks[:, i]
        rows.append({**e, 'expectedPosition': round(float(r.mean()), 3),
                     'low': float(np.quantile(r, .03)), 'high': float(np.quantile(r, .97)),
                     'distribution': [round(float(np.mean(r == p)), 6) for p in range(1, len(entrants) + 1)]})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'raceId': race_id, 'cutoff': cutoff, 'kind': 'retrospective-held-out',
        'conditionalOn': 'No technical retirement; latent outcome score simulation, not a telemetry model',
        'seed': 20261110, 'simulations': len(ranks), 'drivers': rows}, separators=(',', ':')))
