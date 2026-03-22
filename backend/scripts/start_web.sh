#!/bin/sh

# Arranque simple: en debug conservamos runserver para ergonomía local;
# fuera de debug usamos gunicorn para no exponer el VPS a un servidor de desarrollo.
if [ "${DJANGO_DEBUG:-0}" = "1" ]; then
  exec python manage.py runserver 0.0.0.0:8000
fi

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${WEB_CONCURRENCY:-3}" \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --access-logfile - \
  --error-logfile -
