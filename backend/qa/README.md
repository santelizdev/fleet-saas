# QA Manual Alpha MVP (E2E)

## 0) Pre-requisitos
- Stack arriba: `docker compose up -d`
- API accesible en `http://localhost:8100`
- `jq` instalado para script curl

## 1) Preparar datos QA
```bash
cd backend
./scripts/qa_prepare_alpha_data.sh
```
Salida esperada (ejemplo):
`QA_READY company_id=1 user_email=qa-admin@fleet.local vehicle_id=1 vehicle_plate=QA-1001`

## 2) Opción A: Script curl E2E
```bash
cd backend
./qa/curl/alpha_e2e.sh
```
Flujo incluido:
1. Import CSV de vehículos
2. Crear documento
3. Renovar documento
4. `generate_daily_alerts`
5. Listar alerts
6. `acknowledge` / `resolve`
7. `process_notifications`
8. Consultar notificaciones
9. Workflow gastos: reportar -> aprobar -> pagar
10. Consultar dashboard + costos
11. Export CSV

Variables útiles:
```bash
BASE_URL=http://localhost:8100 AUTH_EMAIL=qa-admin@fleet.local AUTH_PASSWORD='QaPass123!' VEHICLE_ID=1 ./qa/curl/alpha_e2e.sh
```

## 3) Opción B: Postman
Importar:
- `qa/postman/alpha-mvp-e2e.postman_collection.json`
- `qa/postman/alpha-mvp-local.postman_environment.json`

Orden sugerido de ejecución en Postman:
1. `Health`
2. `Create Vehicle Document`
3. `Renew Vehicle Document`
4. Ejecutar en terminal: `docker compose run --rm web python manage.py generate_daily_alerts`
5. `List Document Alerts`
6. `Acknowledge Document Alert`
7. `Resolve Document Alert`
8. Ejecutar en terminal: `docker compose run --rm web python manage.py process_notifications --limit=100 --max-attempts=5`
9. `List Notifications`
10. `Report Dashboard`
11. `Report Vehicle Costs`
12. `Report Vehicle Costs CSV`

Notas:
- La colección usa Basic Auth (`auth_email`/`auth_password`).
- `vehicle_document_id`, `document_alert_id` y `notification_id` se guardan automáticamente en variables de entorno.
