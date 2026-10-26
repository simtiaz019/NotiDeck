#!/usr/bin/env sh
set -eu
: "${NOTIDECK_API_KEY:?Set the source API key}"
curl --fail-with-body "${NOTIDECK_URL:-http://127.0.0.1:8000}/api/v1/notifications" \
  -H "Authorization: Bearer $NOTIDECK_API_KEY" -H 'Content-Type: application/json' \
  -d '{"environment":"staging","severity":"ERROR","title":"Backup failed","message":"Review backup service logs."}'
