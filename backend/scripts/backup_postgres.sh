#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR=${1:-/var/backups/fleet}
TS=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

# Requiere docker compose y contenedor db levantado.
docker compose exec -T db pg_dump -U fleet -d fleet -Fc > "$BACKUP_DIR/fleet_${TS}.dump"

echo "Backup creado: $BACKUP_DIR/fleet_${TS}.dump"
