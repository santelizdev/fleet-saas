# Infra MVP (Semana 8)

## Gunicorn (systemd)
1. Copiar `infra/systemd/gunicorn.service` a `/etc/systemd/system/gunicorn.service`.
2. Ajustar rutas `/opt/fleet` según tu VPS.
3. Ejecutar:
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable gunicorn`
   - `sudo systemctl start gunicorn`

## Nginx
1. Copiar `infra/nginx/fleet.conf` a `/etc/nginx/sites-available/fleet.conf`.
2. Habilitar el sitio y recargar Nginx.

## Logrotate
1. Copiar `infra/logrotate/fleet` a `/etc/logrotate.d/fleet`.

## Backups
- Backup: `./scripts/backup_postgres.sh /var/backups/fleet`
- Restore: `./scripts/restore_postgres.sh /var/backups/fleet/fleet_YYYYMMDD_HHMMSS.dump`

## Cron sugerido
- Backup diario 03:00:
  `0 3 * * * /opt/fleet/backend/scripts/backup_postgres.sh /var/backups/fleet`
- Generación de alertas diaria 08:00:
  `0 8 * * * cd /opt/fleet && docker compose run --rm web python manage.py generate_daily_alerts`
- Procesar notificaciones cada 5 min:
  `*/5 * * * * cd /opt/fleet && docker compose run --rm web python manage.py process_notifications --limit=100 --max-attempts=5`
