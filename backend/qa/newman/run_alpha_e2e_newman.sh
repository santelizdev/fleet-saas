#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT_DIR"

COLLECTION="qa/postman/alpha-mvp-e2e.postman_collection.json"
ENV_FILE="qa/postman/alpha-mvp-local.postman_environment.json"
NEWMAN_BASE_URL=${NEWMAN_BASE_URL:-http://host.docker.internal:8100}
export NEWMAN_BASE_URL

if ! docker image inspect postman/newman:alpine >/dev/null 2>&1; then
  echo "Pulling postman/newman:alpine..."
  docker pull postman/newman:alpine >/dev/null
fi

echo "[newman 0/6] Prepare QA data"
docker compose up -d >/dev/null
./scripts/qa_prepare_alpha_data.sh >/tmp/qa_prepare.out
cat /tmp/qa_prepare.out
VEHICLE_ID=$(grep -Eo 'vehicle_id=[0-9]+' /tmp/qa_prepare.out | tail -1 | cut -d= -f2)
[[ -n "$VEHICLE_ID" ]] || { echo "No VEHICLE_ID"; exit 1; }
export VEHICLE_ID

cp "$ENV_FILE" /tmp/alpha-mvp-local.postman_environment.json
python3 - <<'PY'
import json
p='/tmp/alpha-mvp-local.postman_environment.json'
with open(p) as f:
    d=json.load(f)
for v in d['values']:
    if v['key']=='vehicle_id':
        v['value']=str(__import__('os').environ['VEHICLE_ID'])
    if v['key']=='base_url':
        v['value']=__import__('os').environ['NEWMAN_BASE_URL']
with open(p,'w') as f:
    json.dump(d,f,indent=2)
PY

echo "[newman 1/6] Phase 1 - Setup"
docker run --rm -v "$ROOT_DIR":/etc/newman -v /tmp:/tmp postman/newman:alpine run \
  "/etc/newman/$COLLECTION" \
  --environment /tmp/alpha-mvp-local.postman_environment.json \
  --folder "Phase 1 - Setup"

echo "[newman 2/6] generate_daily_alerts"
docker compose run --rm web python manage.py generate_daily_alerts

echo "[newman 3/6] Phase 2 - Alerts & Notifications"
docker run --rm -v "$ROOT_DIR":/etc/newman -v /tmp:/tmp postman/newman:alpine run \
  "/etc/newman/$COLLECTION" \
  --environment /tmp/alpha-mvp-local.postman_environment.json \
  --folder "Phase 2 - Alerts & Notifications"

echo "[newman 4/6] process_notifications"
docker compose run --rm web python manage.py process_notifications --limit=100 --max-attempts=5

echo "[newman 5/6] Phase 3 - Expenses"
docker run --rm -v "$ROOT_DIR":/etc/newman -v /tmp:/tmp postman/newman:alpine run \
  "/etc/newman/$COLLECTION" \
  --environment /tmp/alpha-mvp-local.postman_environment.json \
  --folder "Phase 3 - Expenses"

echo "[newman 6/6] Phase 4 - Reports"
docker run --rm -v "$ROOT_DIR":/etc/newman -v /tmp:/tmp postman/newman:alpine run \
  "/etc/newman/$COLLECTION" \
  --environment /tmp/alpha-mvp-local.postman_environment.json \
  --folder "Phase 4 - Reports"

echo "Newman E2E finalizado OK"
