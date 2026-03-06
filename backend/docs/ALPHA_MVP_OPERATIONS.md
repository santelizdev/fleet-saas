# Alpha MVP - Guía Operativa (1 página)

## Objetivo
Operar pilotos (3-5 empresas) sin degradar estabilidad, con soporte y trazabilidad.

## Checklist de arranque
1. `docker compose up -d`
2. `docker compose run --rm web python manage.py migrate`
3. `docker compose run --rm web python manage.py seed_rbac`
4. Validar:
   - `GET /health/`
   - login admin
   - `python manage.py check`

## Flujo funcional mínimo para cliente
1. Onboarding express (interno): `POST /api/internal/superadmin/onboarding/quickstart/`
2. Carga vehículos:
   - manual: `POST /api/vehicles/`
   - CSV: `POST /api/vehicles/import-csv/`
3. Pack documental: `POST /api/documents/vehicle-documents/create-pack/`
4. Renovación + adjunto:
   - `POST /api/documents/vehicle-documents/{id}/renew/`
   - `POST /api/documents/attachments/`
5. Gastos workflow:
   - reportar: `POST /api/expenses/vehicle-expenses/`
   - aprobar/rechazar: `POST /api/expenses/vehicle-expenses/{id}/approve|reject/`
   - pagar: `POST /api/expenses/vehicle-expenses/{id}/pay/`

## Jobs operativos
- Generar alertas:
  `python manage.py generate_daily_alerts`
- Procesar notificaciones:
  `python manage.py process_notifications --limit=100 --max-attempts=5`
- Ver estado jobs y fallas:
  `GET /api/internal/superadmin/overview/`

## Límites por empresa
- `max_vehicles`
- `max_uploads_per_day`
- `max_storage_mb`
- `max_exports_per_day`

Cuando se exceden:
- API retorna `403`/`429`
- se registra `AuditLog` (`limit.*.exceeded`)

## Soporte formal
- Email soporte: `support@fleet.local` (configurable por env `SUPPORT_EMAIL`)
- WhatsApp soporte: `+56 9 0000 0000` (configurable por env `SUPPORT_WHATSAPP`)
- SLA alpha sugerido: respuesta inicial en <= 24h hábil

## Operación ante incidente
1. Revisar `JobRun` y notificaciones fallidas en panel superadmin.
2. Corregir y reintentar `process_notifications`.
3. Verificar impacto por empresa (storage/fallas/exports).
4. Reportar causa + acción en canal de soporte.

## Backup / Restore
- Backup: `./scripts/backup_postgres.sh /var/backups/fleet`
- Restore: `./scripts/restore_postgres.sh /var/backups/fleet/fleet_YYYYMMDD_HHMMSS.dump`
