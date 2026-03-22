import os

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

import redis

from .forms import QuoteRequestForm


def home_landing(request):
    """
    Home público simple para demo/captación.

    Mantiene el proyecto navegable para prospectos sin mezclar el admin con el
    sitio marketing y deja un formulario de cotización funcional para el MVP.
    """

    if request.method == "POST":
        form = QuoteRequestForm(request.POST)
        if form.is_valid():
            payload = form.cleaned_data
            subject = f"{_('Nueva cotización Fleet')}: {payload['company_name']}"
            body = (
                f"{_('Nueva solicitud desde la landing de Fleet SaaS')}\n\n"
                f"{_('Nombre')}: {payload['full_name']}\n"
                f"{_('Empresa')}: {payload['company_name']}\n"
                f"Email: {payload['email']}\n"
                f"{_('Teléfono')}: {payload['phone']}\n"
                f"{_('Vehículos')}: {payload['fleet_size']}\n\n"
                f"{_('Contexto')}:\n{payload['message'] or _('Sin comentario adicional.')}\n"
            )
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [settings.SUPPORT_EMAIL],
                fail_silently=True,
            )
            messages.success(request, _("Recibimos tu solicitud. Te contactaremos a la brevedad."))
            return redirect("home")
    else:
        form = QuoteRequestForm()

    return render(
        request,
        "public/home_landing.html",
        {
            "quote_form": form,
            "marketing_stats": [
                {"value": "+10", "label": _("Módulos operativos")},
                {"value": "24/7", "label": _("Visibilidad de flota")},
                {"value": "<48h", "label": _("Tiempo de puesta en marcha")},
            ],
        },
    )


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
