#!/usr/bin/env bash
# Run SQL against ClickHouse Cloud using credentials from .env
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
curl -sS --max-time "${CH_TIMEOUT:-900}" \
  --user "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" \
  --data-binary "${1:-SELECT 1}" \
  "https://${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT}/?database=${CLICKHOUSE_DATABASE}"
