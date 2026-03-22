# Despliegue a servidor y habilitación de notificaciones

## Objetivo
Subir esta versión al servidor, aplicar migraciones nuevas y dejar listo el entorno para probar:

- Admin modernizado
- Centro de reportes
- Alertas con mensajes internos (`in_app`) y notificaciones `email`

## Importante: el proyecto hoy soporta 2 modos de despliegue

### Opción A: Docker Compose
Es la opción más alineada con el estado actual del repositorio.

- `web` escucha dentro del contenedor en `8000`
- se expone al host en `18100`
- PostgreSQL se expone en `5542`
- Redis se expone en `6380`

Si usas Nginx delante de Docker, el proxy debe apuntar a:

`http://127.0.0.1:18100`

### Opción B: systemd + gunicorn
También existe infraestructura base para esta modalidad.

- gunicorn escucha en `127.0.0.1:8000`
- en este caso Nginx debe apuntar a `http://127.0.0.1:8000`

No mezclar ambos targets en Nginx al mismo tiempo.

## Checklist recomendado para subir a servidor con Docker

1. Subir cambios al servidor:

```bash
cd /opt/fleet
git pull origin main
```

2. Actualizar `.env` del servidor:

- Puedes partir copiando `.env.example`
- Ajusta dominio, secretos y SMTP

```bash
cp .env.example .env
```

3. Reconstruir y levantar servicios:

```bash
docker compose up -d --build
```

4. Aplicar migraciones:

```bash
docker compose exec web python manage.py migrate
```

5. Recolectar estáticos si luego migras a gunicorn/nginx fuera de Docker:

```bash
docker compose exec web python manage.py collectstatic --noinput
```

6. Validar salud básica:

```bash
curl http://127.0.0.1:18100/health/
```

7. Entrar al admin:

`http://TU_HOST:18100/admin/`

Si tienes Nginx delante, sería:

`https://tu-dominio.com/admin/`

## Variables de entorno nuevas relevantes

### Email

- `DEFAULT_FROM_EMAIL`
- `DJANGO_EMAIL_BACKEND`
- `DJANGO_EMAIL_HOST`
- `DJANGO_EMAIL_PORT`
- `DJANGO_EMAIL_HOST_USER`
- `DJANGO_EMAIL_HOST_PASSWORD`
- `DJANGO_EMAIL_USE_TLS`
- `DJANGO_EMAIL_USE_SSL`

### Alertas programadas

- `ALERT_DEFAULT_MAINTENANCE_REMINDER_DAYS`
- `ALERT_DEFAULT_MAINTENANCE_REMINDER_KM`

## Cómo probar email de notificaciones

## Paso 1: dejar SMTP real
Configura en `.env` un backend SMTP real, por ejemplo:

```env
DEFAULT_FROM_EMAIL=notificaciones@tu-dominio.com
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=smtp.tu-proveedor.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_HOST_USER=notificaciones@tu-dominio.com
DJANGO_EMAIL_HOST_PASSWORD=TU_PASSWORD_SMTP
DJANGO_EMAIL_USE_TLS=1
DJANGO_EMAIL_USE_SSL=0
```

## Paso 2: generar alertas
Las notificaciones email se crean cuando `generate_daily_alerts` detecta vencimientos o próximos vencimientos.

```bash
docker compose exec web python manage.py generate_daily_alerts
```

## Paso 3: procesar la cola

```bash
docker compose exec web python manage.py process_notifications --limit=100 --max-attempts=5
```

## Paso 4: revisar resultados

- Admin > Alertas > Notificaciones
- Verifica `channel=email`
- Si hubo error, revisa `last_error`

## Jobs que debes programar en servidor

### Generación diaria de alertas
Recomendado una vez por día:

```bash
0 8 * * * cd /opt/fleet && docker compose exec -T web python manage.py generate_daily_alerts
```

### Procesamiento de cola de notificaciones
Recomendado una primera corrida justo después de generar alertas y otra vespertina para reintentos:

```bash
5 8 * * * cd /opt/fleet && docker compose exec -T web python manage.py process_notifications --limit=200 --max-attempts=5
5 15 * * * cd /opt/fleet && docker compose exec -T web python manage.py process_notifications --limit=200 --max-attempts=5
```

`exec -T` evita problemas de TTY en cron.

## Validación mínima post deploy

1. `/health/` responde OK
2. `/admin/` carga correctamente
3. `python manage.py migrate` no deja pendientes
4. `generate_daily_alerts` crea registros en `JobRun`
5. `process_notifications` marca `email`/`in_app` como `sent` o deja error legible en `last_error`

## Comandos útiles de diagnóstico

Ver logs web:

```bash
docker compose logs -f web
```

Ver migraciones pendientes:

```bash
docker compose exec web python manage.py showmigrations
```

Entrar a shell Django:

```bash
docker compose exec web python manage.py shell
```

## Recomendación práctica de arranque

Primero prueba así:

1. SMTP real funcionando
2. correr `generate_daily_alerts`
3. correr `process_notifications`
4. revisar `Notification`, `JobRun` y logs

Con eso validas:

- creación de alertas
- envío por email
- fanout a mensajes internos
- trazabilidad operativa
