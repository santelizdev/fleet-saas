import os
from django.http import JsonResponse
from django.db import connection

import redis


def health_check(request):
    """
    Endpoint mínimo de salud para operación.

    Devuelve:
    - db: ok/degraded
    - redis: ok/degraded

    Si quieres hacerlo más estricto, puedes retornar HTTP 500 si algo falla.
    Por ahora retorna 200 con detalle, para diagnosticar fácil en desarrollo.
    """

    result = {"status": "ok", "db": "ok", "redis": "ok"}

    # DB check: un SELECT 1 simple
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
    except Exception:
        result["status"] = "degraded"
        result["db"] = "degraded"

    # Redis check: ping
    try:
        r = redis.from_url(os.environ["REDIS_URL"], socket_timeout=1)
        r.ping()
    except Exception:
        result["status"] = "degraded"
        result["redis"] = "degraded"

    return JsonResponse(result)