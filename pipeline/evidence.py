"""Fetch structured public evidence. Never scrape or redistribute journalism."""
from datetime import datetime, timedelta
import json
import statistics
from urllib.parse import urlencode
from .common import fetch, digest


def openf1(endpoint, **query):
    url = 'https://api.openf1.org/v1/' + endpoint + '?' + urlencode(query)
    raw = fetch(url, limit=12 * 1024 * 1024)
    return json.loads(raw), {'id': endpoint, 'url': url, 'sha256': digest(raw)}


def collect(race, results, directory):
    directory.mkdir(parents=True, exist_ok=True)
    sessions, source = openf1('sessions', **{'year': race['year'], 'session_name': 'Race', 'date_start>': race['date'], 'date_start<': race['date'] + 'T23:59:59'})
    if len(sessions) != 1:
        raise ValueError('Cannot identify a unique race session; hold article for review')
    key = sessions[0]['session_key']
    sources = [source]
    datasets = {}
    for endpoint in ['laps', 'stints', 'pit', 'race_control', 'weather', 'team_radio', 'drivers']:
        datasets[endpoint], source = openf1(endpoint, session_key=key)
        sources.append(source)
        (directory / f'{endpoint}.json').write_text(json.dumps(datasets[endpoint]))
    if len(datasets['laps']) < 20 or len(datasets['drivers']) < len(results):
        raise ValueError('Incomplete timing evidence')
    names = {d['driver_number']: d['full_name'] for d in datasets['drivers']}
    # Match neutralisation timestamps rather than leader lap numbers.
    neutral, start = [], None
    for r in sorted(datasets['race_control'], key=lambda x: x['date']):
        m = r['message'].upper()
        if 'DEPLOYED' in m and ('VSC' in m or 'SAFETY CAR' in m):
            start = datetime.fromisoformat(r['date'])
        if start and ('VSC ENDING' in m or 'SAFETY CAR IN THIS LAP' in m):
            neutral.append((start, datetime.fromisoformat(r['date']) + timedelta(seconds=120)))
            start = None
    if start:
        neutral.append((start, datetime.max.replace(tzinfo=start.tzinfo)))
    pit_laps = {(p['driver_number'], p['lap_number']) for p in datasets['pit']}
    metrics = []
    for number, name in names.items():
        good = []
        for lap in datasets['laps']:
            t, date = lap.get('lap_duration'), lap.get('date_start')
            if lap['driver_number'] != number or not t or not date or lap['lap_number'] == 1 or lap.get('is_pit_out_lap'):
                continue
            if (number, lap['lap_number']) in pit_laps:
                continue
            a = datetime.fromisoformat(date)
            b = a + timedelta(seconds=t)
            if any(a < end and b > begin for begin, end in neutral):
                continue
            good.append(t)
        if good:
            metrics.append({'name': name, 'driverNumber': number, 'sampleCount': len(good), 'medianLapSeconds': round(statistics.median(good), 3)})
    return {'sessionKey': key, 'sources': sources,
            'limitations': ['Timing medians are descriptive, not fuel-, tyre-, traffic- or damage-adjusted pace.',
                           'Neutralisation exclusion includes a conservative 120-second release buffer.',
                           'Deleted laps are not reconstructed in this initial metric; do not use medians as driver skill rankings.',
                           'Radio catalogue contains audio links only. No radio content has been transcribed or verified.',
                           'No journalism ingested; narrative is derived from structured timing and race-control messages.'],
            'lapMetrics': metrics, 'stints': datasets['stints'],
            'timeline': [{'date': r['date'], 'message': r['message']} for r in datasets['race_control']],
            'radioCount': len(datasets['team_radio'])}
