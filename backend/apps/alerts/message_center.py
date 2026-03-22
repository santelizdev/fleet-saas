"""Servicios del centro de mensajes para el admin y futuras vistas operativas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext_lazy as _

from apps.alerts.models import JobRun, Notification
from apps.alerts.services import build_notification_content


@dataclass
class MessageCenterFilters:
    """Normaliza filtros del centro de mensajes sin acoplarlos al request."""

    company_id: int | None
    date_from: object
    date_to: object
    channel: str
    status: str
    query: str


MESSAGE_CHANNEL_CHOICES = [
    ("all", _("Todos")),
    (Notification.CHANNEL_IN_APP, _("Internos")),
    (Notification.CHANNEL_EMAIL, _("Correo")),
]

MESSAGE_STATUS_CHOICES = [
    ("all", _("Todos")),
    (Notification.STATUS_QUEUED, _("En cola")),
    (Notification.STATUS_SENT, _("Enviados")),
    (Notification.STATUS_FAILED, _("Fallidos")),
]


def build_message_center_filters(params, *, company_id: int | None) -> MessageCenterFilters:
    """Parsea filtros simples para el módulo de mensajes del backoffice."""
    today = timezone.localdate()
    date_from = parse_date(params.get("date_from") or "") or (today - timedelta(days=30))
    date_to = parse_date(params.get("date_to") or "") or today
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    channel = params.get("channel") or "all"
    if channel not in {value for value, _ in MESSAGE_CHANNEL_CHOICES}:
        channel = "all"

    status = params.get("status") or "all"
    if status not in {value for value, _ in MESSAGE_STATUS_CHOICES}:
        status = "all"

    return MessageCenterFilters(
        company_id=company_id,
        date_from=date_from,
        date_to=date_to,
        channel=channel,
        status=status,
        query=(params.get("q") or "").strip(),
    )


def _notification_scope(filters: MessageCenterFilters):
    """Entrega un queryset ya scopeado para renderizar el centro de mensajes."""
    qs = Notification.objects.select_related(
        "document_alert",
        "document_alert__vehicle_document__vehicle",
        "document_alert__driver_license__driver",
        "maintenance_alert",
        "maintenance_alert__vehicle",
    ).filter(created_at__date__range=(filters.date_from, filters.date_to))
    if filters.company_id is not None:
        qs = qs.filter(company_id=filters.company_id)
    if filters.channel != "all":
        qs = qs.filter(channel=filters.channel)
    if filters.status != "all":
        qs = qs.filter(status=filters.status)
    if filters.query:
        qs = qs.filter(
            Q(recipient__icontains=filters.query)
            | Q(last_error__icontains=filters.query)
            | Q(document_alert__message__icontains=filters.query)
            | Q(maintenance_alert__message__icontains=filters.query)
        )
    return qs.order_by("-created_at", "-id")


def _serialize_message_card(notification: Notification) -> dict:
    """Prepara una fila simple y estable para el admin sin lógica en el template."""
    subject, body, payload = build_notification_content(notification)
    return {
        "id": notification.id,
        "channel": notification.channel,
        "channel_label": notification.get_channel_display(),
        "status": notification.status,
        "status_label": notification.get_status_display(),
        "recipient": notification.recipient or _("Sin destinatario"),
        "subject": subject,
        "body": body,
        "context": payload.get("context", ""),
        "entity": payload.get("entity", ""),
        "alert_id": payload.get("alert_id"),
        "attempts": notification.attempts,
        "last_error": notification.last_error,
        "available_at": notification.available_at,
        "sent_at": notification.sent_at,
        "created_at": notification.created_at,
    }


def build_message_center_context(filters: MessageCenterFilters) -> dict:
    """Arma el contexto consolidado del módulo de mensajes internos y emails."""
    messages = _notification_scope(filters)
    recent_jobs = JobRun.objects.filter(job_name__in=["generate_daily_alerts", "process_notifications"]).order_by("-created_at")

    kpis = {
        "total": messages.count(),
        "internal": messages.filter(channel=Notification.CHANNEL_IN_APP).count(),
        "emails": messages.filter(channel=Notification.CHANNEL_EMAIL).count(),
        "queued": messages.filter(status=Notification.STATUS_QUEUED).count(),
        "sent": messages.filter(status=Notification.STATUS_SENT).count(),
        "failed": messages.filter(status=Notification.STATUS_FAILED).count(),
    }

    recent_serialized = [_serialize_message_card(item) for item in messages[:18]]
    internal_serialized = [item for item in recent_serialized if item["channel"] == Notification.CHANNEL_IN_APP][:8]
    email_serialized = [item for item in recent_serialized if item["channel"] == Notification.CHANNEL_EMAIL][:8]
    failed_serialized = [item for item in recent_serialized if item["status"] == Notification.STATUS_FAILED][:8]

    return {
        "message_filters": filters,
        "message_channel_choices": MESSAGE_CHANNEL_CHOICES,
        "message_status_choices": MESSAGE_STATUS_CHOICES,
        "message_kpis": kpis,
        "message_recent": recent_serialized,
        "message_internal_recent": internal_serialized,
        "message_email_recent": email_serialized,
        "message_failed_recent": failed_serialized,
        "message_recent_jobs": recent_jobs[:8],
    }
