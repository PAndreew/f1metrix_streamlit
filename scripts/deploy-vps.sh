#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VPS_IP="${VPS_IP:-46.62.236.54}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/hetzner_new}"
REMOTE_ROOT="${REMOTE_ROOT:-/opt/f1metrix}"
F1METRIX_HOST="${F1METRIX_HOST:-f1metrix.46-62-236-54.sslip.io}"
SSH=(ssh -i "$SSH_KEY" root@"$VPS_IP")
RSYNC=(rsync -az --delete -e "ssh -i $SSH_KEY")

"${SSH[@]}" "mkdir -p '$REMOTE_ROOT'"
"${RSYNC[@]}" --exclude=.git --exclude=node_modules --exclude=legacy \
  --exclude=data/model-output.json --exclude=data/f1db.db --exclude=model/artifacts \
  "$ROOT/" "root@$VPS_IP:$REMOTE_ROOT/"
"${SSH[@]}" "chmod +x '$REMOTE_ROOT/scripts/run_model_update.sh'; cd '$REMOTE_ROOT'; docker compose -f compose.production.yml build web model; docker compose -f compose.production.yml up -d web"

"${SSH[@]}" "cat > /etc/cron.d/f1metrix <<'EOF'
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# F1DB publishes a new tagged release after race data is added. The updater exits
# without fitting when the release tag is unchanged.
17 4 * * * root /opt/f1metrix/scripts/run_model_update.sh >> /var/log/f1metrix-model.log 2>&1
EOF
chmod 644 /etc/cron.d/f1metrix"

"${SSH[@]}" "python3 - <<'PY'
from pathlib import Path
host='$F1METRIX_HOST'
path=Path('/opt/bleeek/deploy/Caddyfile')
text=path.read_text()
block=f'''\n\n{host} {{
    encode zstd gzip
    reverse_proxy f1metrix-web:8080
    header {{
        Permissions-Policy \"camera=(), microphone=(), geolocation=()\"
        X-Frame-Options \"DENY\"
    }}
}}\n'''
if host not in text:path.write_text(text.rstrip()+block)
PY
docker exec bleeek-caddy-1 caddy reload --config /etc/caddy/Caddyfile"

for _ in $(seq 1 40); do curl -fsS "https://$F1METRIX_HOST/health" >/dev/null && { echo "Deployed: https://$F1METRIX_HOST"; exit 0; }; sleep 3; done
echo "Deployment health check failed" >&2; exit 1
