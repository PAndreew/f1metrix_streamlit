"""Small, bounded HTTP and atomic-file helpers. No runtime web dependencies."""
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request


def fetch(url, *, body=None, headers=None, limit=64 * 1024 * 1024):
    headers = {'User-Agent': 'f1metrix-publication/1', **(headers or {})}
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=90) as response:
                data = response.read(limit + 1)
            if len(data) > limit:
                raise ValueError('Response exceeds configured byte limit')
            return data
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise
        except (TimeoutError, urllib.error.URLError):
            if attempt == 3:
                raise
        time.sleep(2 ** attempt * 3)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False))
    os.replace(tmp, path)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def latest_release():
    token = os.getenv('GITHUB_TOKEN')
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    return json.loads(fetch('https://api.github.com/repos/f1db/f1db/releases/latest', headers=headers))


def require_fit(snapshot):
    d = snapshot['metadata']['diagnostics']
    if not all(k in d for k in ('maxRhat', 'minEssBulk', 'divergences')):
        raise ValueError('Missing MCMC diagnostics; approximate/legacy fits cannot publish')
    if not (0 < d['maxRhat'] <= 1.01 and d['minEssBulk'] >= 400 and d['divergences'] == 0):
        raise ValueError(f'Fit failed publication gate: {d}')
