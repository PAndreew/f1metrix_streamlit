#!/usr/bin/env sh
set -eu
cd "${F1METRIX_ROOT:-/opt/f1metrix}"
exec flock -n /run/f1metrix-model.lock \
  docker compose --profile model -f compose.production.yml run --rm model
