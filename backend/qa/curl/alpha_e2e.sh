#!/usr/bin/env bash
set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo "jq es requerido para este script." >&2
  exit 1
fi

BASE_URL=${BASE_URL:-http://localhost:8100}
AUTH_EMAIL=${AUTH_EMAIL:-qa-admin@fleet.local}
AUTH_PASSWORD=${AUTH_PASSWORD:-QaPass123!}
VEHICLE_ID=${VEHICLE_ID:-}

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT_DIR"

echo "[1/11] Preparando data QA..."
PREP_OUTPUT=$(QA_EMAIL="$AUTH_EMAIL" QA_PASSWORD="$AUTH_PASSWORD" ./scripts/qa_prepare_alpha_data.sh)
echo "$PREP_OUTPUT"

if [[ -z "$VEHICLE_ID" ]]; then
  VEHICLE_ID=$(echo "$PREP_OUTPUT" | grep -Eo 'vehicle_id=[0-9]+' | tail -1 | cut -d= -f2)
fi

if [[ -z "$VEHICLE_ID" ]]; then
  echo "No pude resolver VEHICLE_ID." >&2
  exit 1
fi

TODAY=$(date +%F)
YESTERDAY=$(date -v-1d +%F 2>/dev/null || date -d 'yesterday' +%F)

auth_curl() {
  local method=$1
  local url=$2
  local data=${3:-}
  if [[ -n "$data" ]]; then
    curl -sS -u "$AUTH_EMAIL:$AUTH_PASSWORD" -H 'Content-Type: application/json' -X "$method" "$url" -d "$data"
  else
    curl -sS -u "$AUTH_EMAIL:$AUTH_PASSWORD" -X "$method" "$url"
  fi
}

echo "[2/11] Importar vehiculos por CSV..."
CSV_PAYLOAD=$(jq -n --arg csv "plate,brand,model,current_km\nQA-2001,Toyota,Yaris,1000\nQA-2002,Kia,Rio,1500\n" '{csv_content:$csv}')
CSV_JSON=$(auth_curl POST "$BASE_URL/api/vehicles/import-csv/" "$CSV_PAYLOAD")
CSV_SUMMARY=$(echo "$CSV_JSON" | jq -r 'if type=="object" and has("created") then "\(.created)/\(.existing)" else "" end')
if [[ -z "$CSV_SUMMARY" ]]; then
  echo "Fallo import CSV: $CSV_JSON"
  exit 1
fi
echo "csv import created/existing: $CSV_SUMMARY"

echo "[3/11] Crear VehicleDocument..."
CREATE_DOC_PAYLOAD=$(jq -n \
  --argjson vehicle "$VEHICLE_ID" \
  --arg issue "$YESTERDAY" \
  --arg expiry "$TODAY" \
  '{vehicle:$vehicle, type:"seguro", issue_date:$issue, expiry_date:$expiry, reminder_days_before:0, notes:"qa-e2e-doc"}')
DOC_JSON=$(auth_curl POST "$BASE_URL/api/documents/vehicle-documents/" "$CREATE_DOC_PAYLOAD")
DOC_ID=$(echo "$DOC_JSON" | jq -r '.id // empty')
[[ -n "$DOC_ID" ]] || { echo "Fallo creando documento: $DOC_JSON"; exit 1; }
echo "Documento creado id=$DOC_ID"

echo "[4/11] Renew document..."
# Para QA E2E forzamos vencimiento hoy para que generate_daily_alerts lo tome en la misma corrida.
RENEW_PAYLOAD=$(jq -n --arg issue "$YESTERDAY" --arg expiry "$TODAY" --arg notes "qa-renew" '{issue_date:$issue, expiry_date:$expiry, notes:$notes}')
RENEW_JSON=$(auth_curl POST "$BASE_URL/api/documents/vehicle-documents/$DOC_ID/renew/" "$RENEW_PAYLOAD")
RENEW_ID=$(echo "$RENEW_JSON" | jq -r '.id // empty')
[[ -n "$RENEW_ID" ]] || { echo "Fallo renew: $RENEW_JSON"; exit 1; }
echo "Documento renovado id=$RENEW_ID"

echo "[5/11] Ejecutar generate_daily_alerts..."
docker compose run --rm web python manage.py generate_daily_alerts >/tmp/generate_daily_alerts.log
cat /tmp/generate_daily_alerts.log

echo "[6/11] Listar document alerts y hacer acknowledge/resolve..."
ALERTS_JSON=$(auth_curl GET "$BASE_URL/api/alerts/document-alerts/")
ALERT_ID=$(echo "$ALERTS_JSON" | jq -r 'if type=="array" then (.[0].id // empty) else (.results[0].id // empty) end')
[[ -n "$ALERT_ID" ]] || { echo "No hay alerts para operar: $ALERTS_JSON"; exit 1; }
ACK_JSON=$(auth_curl POST "$BASE_URL/api/alerts/document-alerts/$ALERT_ID/acknowledge/")
RESOLVE_JSON=$(auth_curl POST "$BASE_URL/api/alerts/document-alerts/$ALERT_ID/resolve/")
echo "ack: $(echo "$ACK_JSON" | jq -r '.state // .detail')"
echo "resolve: $(echo "$RESOLVE_JSON" | jq -r '.state // .detail')"

echo "[7/11] Ejecutar process_notifications..."
docker compose run --rm web python manage.py process_notifications --limit=100 --max-attempts=5 >/tmp/process_notifications.log
cat /tmp/process_notifications.log

echo "[8/11] Revisar notifications (API)..."
NOTIF_JSON=$(auth_curl GET "$BASE_URL/api/alerts/notifications/")
echo "$NOTIF_JSON" | jq 'if type=="array" then .[:3] else .results[:3] end'

echo "[9/11] Workflow gasto: reportar -> aprobar -> pagar..."
EXP_PAYLOAD=$(jq -n --argjson vehicle "$VEHICLE_ID" --arg d "$TODAY" '{vehicle:$vehicle, amount_clp:150000, expense_date:$d, supplier:"Copec", km:1200, invoice_number:"QA-EXP-001"}')
EXP_JSON=$(auth_curl POST "$BASE_URL/api/expenses/vehicle-expenses/" "$EXP_PAYLOAD")
EXP_ID=$(echo "$EXP_JSON" | jq -r '.id // empty')
[[ -n "$EXP_ID" ]] || { echo "Fallo creando gasto: $EXP_JSON"; exit 1; }
APP_JSON=$(auth_curl POST "$BASE_URL/api/expenses/vehicle-expenses/$EXP_ID/approve/")
PAY_JSON=$(auth_curl POST "$BASE_URL/api/expenses/vehicle-expenses/$EXP_ID/pay/")
echo "expense approval/payment: $(echo "$APP_JSON" | jq -r '.approval_status') / $(echo "$PAY_JSON" | jq -r '.payment_status')"

echo "[10/11] Dashboard report + vehicle-costs..."
DASH_JSON=$(auth_curl GET "$BASE_URL/api/reports/dashboard/")
COSTS_JSON=$(auth_curl GET "$BASE_URL/api/reports/vehicle-costs/")
echo "dashboard: $(echo "$DASH_JSON" | jq '{upcoming_doc_expiries, maintenance_due_30d, maintenance_cost_clp}')"
echo "vehicle-costs rows: $(echo "$COSTS_JSON" | jq '.results | length')"

echo "[11/11] Export CSV report..."
CSV_OUT=/tmp/vehicle_costs_alpha.csv
curl -sS -u "$AUTH_EMAIL:$AUTH_PASSWORD" "$BASE_URL/api/reports/vehicle-costs/export.csv" -o "$CSV_OUT"
head -n 5 "$CSV_OUT"

echo "E2E QA finalizado OK"
