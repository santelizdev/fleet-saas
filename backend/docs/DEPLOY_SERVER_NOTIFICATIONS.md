# Despliegue a servidor y habilitación de notificaciones

## Objetivo
Subir esta versión al servidor, aplicar migraciones nuevas y dejar listo el entorno para probar:

- Admin modernizado
- Centro de reportes
- Alertas con notificaciones `in_app`, `email` y `push`

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
- Ajusta dominio, secretos, SMTP y configuración push

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

### Push

- `NOTIFICATION_PUSH_BACKEND`
- `NOTIFICATION_PUSH_WEBHOOK_URL`
- `NOTIFICATION_PUSH_WEBHOOK_TOKEN`

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

## Cómo probar push notifications

La implementación actual deja el core listo, pero la entrega final depende de un backend push externo.

### Modo 1: `console`
Útil para validar el flujo funcional sin proveedor real.

```env
NOTIFICATION_PUSH_BACKEND=console
```

Con esto:

- se generan notificaciones `push`
- `process_notifications` las marca como enviadas
- el contenido queda trazado en logs del contenedor `web`

### Modo 2: `webhook`
Útil cuando ya tienes un microservicio o endpoint que entrega push real vía:

- FCM
- OneSignal
- Web Push
- APNs gateway propio

Configura:

```env
NOTIFICATION_PUSH_BACKEND=webhook
NOTIFICATION_PUSH_WEBHOOK_URL=https://push.tu-dominio.com/notifications/send
NOTIFICATION_PUSH_WEBHOOK_TOKEN=TOKEN_SEGURO
```

El sistema enviará un `POST` JSON con:

- `title`
- `body`
- `recipient`
- `notification_id`
- `payload`
- `devices`

## Registro de dispositivos push

Para que existan notificaciones `push`, debe haber dispositivos activos registrados en:

- Admin > Alertas > Dispositivos push

O vía API:

- `POST /api/alerts/push-devices/`

Campos base:

- `user`
- `label`
- `provider`
- `token`
- `is_active`

Sin dispositivos activos, el sistema no genera notificaciones push para ese usuario.

## Jobs que debes programar en servidor

### Generación diaria de alertas
Recomendado una vez por día:

```bash
0 8 * * * cd /opt/fleet && docker compose exec -T web python manage.py generate_daily_alerts
```

### Procesamiento de cola de notificaciones
Recomendado cada 5 minutos:

```bash
*/5 * * * * cd /opt/fleet && docker compose exec -T web python manage.py process_notifications --limit=100 --max-attempts=5
```

`exec -T` evita problemas de TTY en cron.

## Validación mínima post deploy

1. `/health/` responde OK
2. `/admin/` carga correctamente
3. `python manage.py migrate` no deja pendientes
4. Existe al menos un `PushDevice` activo para prueba
5. `generate_daily_alerts` crea registros en `JobRun`
6. `process_notifications` marca `email`/`push` como `sent` o deja error legible en `last_error`

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

1. `NOTIFICATION_PUSH_BACKEND=console`
2. SMTP real funcionando
3. registrar 1 dispositivo push en admin
4. correr `generate_daily_alerts`
5. correr `process_notifications`
6. revisar `Notification`, `JobRun` y logs

Con eso validas:

- creación de alertas
- envío por email
- fanout push
- trazabilidad operativa

Luego cambias `push` de `console` a `webhook`.
