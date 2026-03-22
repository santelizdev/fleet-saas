"""Context processors livianos para enriquecer el backoffice sin acoplar vistas."""

from __future__ import annotations

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.alerts.models import Notification
from apps.alerts.services import build_notification_content
from apps.audit.models import AuditLog
from apps.product_analytics.models import ProductEvent


EVENT_LABELS = {
    "expense_reported": "Gasto reportado",
    "expense_approved": "Gasto aprobado",
    "document_renewed": "Documento renovado",
    "attachment_uploaded": "Archivo cargado",
    "vehicle_created": "Vehículo creado",
    "alert_sent": "Alerta generada",
}


def _actor_label(actor) -> str:
    if actor is None:
        return "Sistema"
    return getattr(actor, "name", "") or getattr(actor, "email", "") or "Sistema"


def _company_scope(request, queryset):
    if request.user.is_superuser:
        return queryset
    return queryset.filter(company_id=request.user.company_id)


def admin_recent_activity(request):
    """
    Expone un feed corto de actividad para el header del admin.

    La idea no es replicar un inbox completo, sino entregar un vistazo rápido
    con eventos operacionales recientes y notificaciones emitidas.
    """

    if not request.path.startswith("/admin/"):
        return {}
    if not request.user.is_authenticated:
        return {}

    since = timezone.now() - timedelta(days=2)

    notifications = _company_scope(
        request,
        Notification.objects.select_related(
            "document_alert",
            "maintenance_alert",
        ).filter(created_at__gte=since),
    ).order_by("-created_at")[:5]

    product_events = _company_scope(
        request,
        ProductEvent.objects.select_related("actor").filter(created_at__gte=since),
    ).order_by("-created_at")[:5]

    audit_logs = _company_scope(
        request,
        AuditLog.objects.select_related("actor").filter(created_at__gte=since),
    ).order_by("-created_at")[:4]

    items = []

    for notification in notifications:
        subject, _, payload = build_notification_content(notification)
        items.append(
            {
                "when": notification.created_at,
                "title": subject,
                "subtitle": payload.get("context") or notification.get_channel_display(),
                "meta": notification.get_status_display(),
                "kind": "notification",
                "kind_label": "Mensaje",
                "accent": "var(--fleet-orange)",
                "url": reverse("admin:alerts_notification_overview"),
            }
        )

    for event in product_events:
        items.append(
            {
                "when": event.created_at,
                "title": EVENT_LABELS.get(event.event_name, event.event_name.replace("_", " ").title()),
                "subtitle": event.payload.get("summary") or _actor_label(event.actor),
                "meta": _actor_label(event.actor),
                "kind": "product",
                "kind_label": "Actividad",
                "accent": "var(--fleet-navy)",
                "url": reverse("admin:product_analytics_productevent_changelist"),
            }
        )

    for log in audit_logs:
        items.append(
            {
                "when": log.created_at,
                "title": log.action.replace(".", " ").title(),
                "subtitle": f"{log.object_type}:{log.object_id}",
                "meta": _actor_label(log.actor),
                "kind": "audit",
                "kind_label": "Auditoría",
                "accent": "#5B7AB3",
                "url": reverse("admin:audit_auditlog_changelist"),
            }
        )

    items.sort(key=lambda item: item["when"], reverse=True)
    recent_items = items[:8]

    return {
        "admin_recent_activity_items": recent_items,
        "admin_recent_activity_count": len(recent_items),
        "admin_recent_activity_url": reverse("admin:alerts_notification_overview"),
    }
