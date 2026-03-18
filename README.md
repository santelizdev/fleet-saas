# Fleet SaaS - Alpha MVP

Plataforma SaaS multiempresa para gestión de flota en entorno local/VPS, construida con Django + Docker.

Este repositorio contiene un **Alpha MVP operativo** con foco en:
- onboarding rápido,
- control documental y vencimientos,
- alertas/notificaciones,
- flujo de gastos con trazabilidad,
- límites por empresa para proteger infraestructura,
- observabilidad y operación superadmin,
- QA manual y automatizado (curl/Postman/Newman).

## Estado del proyecto

Alpha funcional con base para pilotos (3-5 empresas), incluyendo:
- multiempresa y scoping por `company`,
- RBAC por capacidades,
- admin Django restringido por empresa,
- salud operativa y jobs schedulables,
- reportes/exportaciones con límites,
- backups y artefactos de despliegue VPS.

## Stack técnico

- Backend: Django 5.0.10 + DRF
- DB: PostgreSQL 16
- Cache/Broker: Redis 7
- Runtime: Docker Compose
- Python: 3.12-slim

## Servicios Docker

`docker-compose.yml` define:
- `web` (Django)
- `db` (Postgres)
- `redis` (Redis)

Puertos por defecto:
- App: `http://localhost:8000`
- Postgres host: `5542`
- Redis host: `6380`

## Módulos implementados

### 1) Identidad, multiempresa y seguridad
- Usuario custom (`AUTH_USER_MODEL`) por email.
- Tenant model: `Company` + `Branch`.
- Middleware de contexto empresa (`request.company`, `request.company_id`).
- RBAC por capacidades (`Capability`, `Role`, `UserRole`).
- Seed RBAC: `python manage.py seed_rbac`.
- Restricción de Django Admin por empresa (queryset + FK scoping).

### 2) Vehículos
- CRUD de vehículos.
- Import masivo por CSV:
  - `POST /api/vehicles/import-csv/`
- Eventos de producto en alta de vehículo (`vehicle_created`).
- Enforcements de límite por plan (`max_vehicles`).

### 3) Documentos y adjuntos
- Modelos:
  - `Attachment`
  - `VehicleDocument` + versionado (`renew`)
  - `DriverLicense` + versionado (`renew`)
  - joins explícitos (sin GFK):
    - `VehicleDocumentAttachment`
    - `DriverLicenseAttachment`
- Validaciones de fechas (`expiry_date > issue_date`) y consistencia company.
- Endpoint pack documental:
  - `POST /api/documents/vehicle-documents/create-pack/`
- Eventos de producto:
  - `document_added`, `document_renewed`, `attachment_uploaded`
- Enforcements de plan en uploads/storage.

### 4) Alertas y notificaciones
- Alertas explícitas:
  - `DocumentAlert`
  - `MaintenanceAlert`
- Notificaciones trazables:
  - `Notification` (`queued/sent/failed`, attempts, last_error, sent_at)
- Commands operativos:
  - `python manage.py generate_daily_alerts`
  - `python manage.py process_notifications --limit=100 --max-attempts=5`
- Retry + backoff + DLQ lógico (`attempts >= N`).
- Acciones API: `acknowledge`, `resolve`, `requeue`.
- Instrumentación de envío (`alert_sent`).

### 5) Mantenimiento y odómetro
- `MaintenanceRecord` (preventivo/correctivo).
- `VehicleOdometerLog` con auto-update de `Vehicle.current_km` cuando entra valor mayor.
- Alertas de mantención por fecha y por km.

### 6) Gastos (workflow completo)
- Modelos:
  - `ExpenseCategory`
  - `VehicleExpense`
  - `VehicleExpenseAttachment`
- Estados:
  - aprobación: `reported -> approved/rejected`
  - pago: `unpaid -> paid`
- Acciones API:
  - reportar, aprobar, rechazar, pagar.
- Regla de negocio:
  - solo se puede pagar un gasto aprobado.
- Auditoría de cambios y eventos:
  - `expense_reported`, `expense_approved`.

### 7) Reportes y export
- Dashboard operativo por empresa:
  - vencimientos 7/15/30,
  - mantenciones próximas,
  - costo mantención período,
  - top vehículos.
- Métrica por vehículo:
  - costo acumulado,
  - costo por km.
- Export CSV:
  - `GET /api/reports/vehicle-costs/export.csv`
- Control de abuso:
  - límite filas/export,
  - límite exports/día,
  - rate limiting por empresa para endpoints caros.

### 8) Operación superadmin
- API interna superadmin:
  - `GET /api/internal/superadmin/overview/`
  - `POST /api/internal/superadmin/onboarding/quickstart/`
- Panel de overview incluye:
  - empresas,
  - jobs últimas 24h,
  - notificaciones fallidas,
  - storage por empresa,
  - activación de empresas (métrica).

### 9) Límites por empresa (plan enforcement)
- `CompanyLimit` por tenant.
- Enforcement real en backend (no solo UI):
  - vehículos,
  - uploads/día,
  - storage total,
  - exports/día.
- Breaches registrados en `AuditLog` (`limit.*.exceeded`).

### 10) Instrumentación de producto
- `ProductEvent` para eventos de uso.
- Eventos implementados:
  - `vehicle_created`
  - `document_added`
  - `document_renewed`
  - `expense_reported`
  - `expense_approved`
  - `alert_sent`
  - `report_exported`
- Base para decisión roadmap con datos reales de uso.

## Endpoints base

- Health:
  - `GET /health/`
- Admin:
  - `GET /admin/`

APIs:
- `/api/vehicles/`
- `/api/documents/`
- `/api/alerts/`
- `/api/expenses/`
- `/api/reports/`
- `/api/internal/` (superadmin)

## Variables de entorno importantes

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DATABASE_URL`
- `REDIS_URL`
- `REPORT_MAX_EXPORT_ROWS`
- `REPORT_MAX_EXPORTS_PER_DAY`
- `RATE_LIMIT_REPORTS_PER_MIN`
- `DEFAULT_MAX_VEHICLES`
- `DEFAULT_MAX_USERS`
- `DEFAULT_MAX_STORAGE_MB`
- `DEFAULT_MAX_UPLOADS_PER_DAY`
- `DEFAULT_MAX_EXPORTS_PER_DAY`
- `SUPPORT_EMAIL`
- `SUPPORT_WHATSAPP`

## Levantar en local

```bash
docker compose up --build -d
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py seed_rbac
docker compose run --rm web python manage.py check
```

Verificar:
- `http://localhost:8000/health/`
- `http://localhost:8000/admin/`

## QA / testing

### Suite automatizada
```bash
docker compose run --rm web python manage.py test -v 2
```

### QA manual (curl)
```bash
cd backend
./qa/curl/alpha_e2e.sh
```

### QA manual (Postman)
- Collection: `backend/qa/postman/alpha-mvp-e2e.postman_collection.json`
- Environment: `backend/qa/postman/alpha-mvp-local.postman_environment.json`

### Runner Newman (automatizado)
```bash
cd backend
./qa/newman/run_alpha_e2e_newman.sh
```

## Operación DevOps/SRE

Artefactos incluidos:
- systemd gunicorn: `backend/infra/systemd/gunicorn.service`
- nginx reverse proxy: `backend/infra/nginx/fleet.conf`
- logrotate: `backend/infra/logrotate/fleet`
- backups:
  - `backend/scripts/backup_postgres.sh`
  - `backend/scripts/restore_postgres.sh`
- guía infra: `backend/infra/README.md`

## Guía operativa alpha

Documento resumido para operación diaria:
- `backend/docs/ALPHA_MVP_OPERATIONS.md`

## Notas

- Este proyecto está optimizado para local/VPS-style (no depende de AWS para funcionar).
- Se priorizó trazabilidad y operabilidad para piloto real.
- El backend ya contempla bases para crecer a beta (límites, observabilidad, QA runner, flujos auditables).
