#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Uso: $0 /ruta/backup.dump"
  exit 1
fi

BACKUP_FILE=$1
if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "No existe: $BACKUP_FILE"
  exit 1
fi

# Cuidado: limpia el schema público antes de restaurar.
docker compose exec -T db psql -U fleet -d fleet -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
docker compose exec -T db pg_restore -U fleet -d fleet --no-owner --no-privileges < "$BACKUP_FILE"

echo "Restore completado desde: $BACKUP_FILE"
