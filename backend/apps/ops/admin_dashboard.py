"""Servicios y callback del dashboard operacional del admin."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.humanize.templatetags.humanize import intcomma
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.alerts.models import AlertState, DocumentAlert, MaintenanceAlert
from apps.audit.models import AuditLog
from apps.documents.models import VehicleDocument
from apps.expenses.models import VehicleExpense
from apps.maintenance.models import MaintenanceRecord
from apps.product_analytics.models import ProductEvent
from apps.tags.services import build_tag_snapshot, get_recent_tag_movements, get_top_tag_vehicles
from apps.vehicles.models import Vehicle

BRAND_SERIES_COLORS = ("#1D2E53", "#F97316", "#5B7AB3", "#D6D8DB", "#F59E0B")


def _company_filter(request) -> dict:
    """Aplica scoping multiempresa para reutilizar el dashboard en superadmin y tenant admin."""
    if request.user.is_superuser:
        return {}
    return {"company_id": request.user.company_id}


def _month_range():
    """Devuelve el primer y último día del mes actual para filtros del dashboard."""
    today = timezone.localdate()
    start = today.replace(day=1)
    next_month = (start + timedelta(days=32)).replace(day=1)
    end = next_month - timedelta(days=1)
    return start, end


def _expiring_documents(filter_kwargs: dict, horizon_days: int = 30):
    """Documentos vigentes próximos a vencer para tarjetas y tabla rápida."""
    today = timezone.localdate()
    horizon = today + timedelta(days=horizon_days)
    return VehicleDocument.objects.select_related("vehicle", "vehicle__assigned_driver").filter(
        is_current=True,
        expiry_date__range=(today, horizon),
        **filter_kwargs,
    )


def _due_maintenance(filter_kwargs: dict, horizon_days: int = 30):
    """Mantenciones abiertas o con próximo vencimiento cercano."""
    today = timezone.localdate()
    horizon = today + timedelta(days=horizon_days)
    return MaintenanceRecord.objects.select_related("vehicle").filter(
        Q(status=MaintenanceRecord.STATUS_OPEN)
        | Q(next_due_date__range=(today, horizon)),
        **filter_kwargs,
    )


def _build_spend_by_category(filter_kwargs: dict):
    """Agrupa el gasto del mes por categoría para la zona analítica del dashboard."""
    month_start, month_end = _month_range()
    return list(
        VehicleExpense.objects.filter(expense_date__range=(month_start, month_end), **filter_kwargs)
        .values("category__name")
        .annotate(total_amount=Coalesce(Sum("amount_clp"), 0), total_items=Count("id"))
        .order_by("-total_amount", "category__name")[:8]
    )


def _build_top_expensive_vehicles(filter_kwargs: dict):
    """Obtiene los vehículos con mayor gasto del mes para accionar rápido."""
    month_start, month_end = _month_range()
    return list(
        VehicleExpense.objects.filter(expense_date__range=(month_start, month_end), **filter_kwargs)
        .values("vehicle_id", "vehicle__plate")
        .annotate(total_amount=Coalesce(Sum("amount_clp"), 0), total_items=Count("id"))
        .order_by("-total_amount", "vehicle__plate")[:5]
    )


def _build_recent_activity(filter_kwargs: dict):
    """Fusiona auditoría y eventos de producto como feed reciente del backoffice."""
    audit_logs = list(
        AuditLog.objects.select_related("actor").filter(**filter_kwargs).order_by("-created_at")[:5]
    )
    product_events = list(
        ProductEvent.objects.select_related("actor").filter(**filter_kwargs).order_by("-created_at")[:5]
    )
    timeline = []
    for log in audit_logs:
        timeline.append(
            {
                "when": log.created_at,
                "title": log.summary or log.action,
                "subtitle": f"{log.object_type}:{log.object_id}",
                "actor": getattr(log.actor, "name", "Sistema") or getattr(log.actor, "email", "Sistema"),
                "source": "audit",
                "source_label": "Auditoría",
                "source_color": "#1D2E53",
            }
        )
    for event in product_events:
        timeline.append(
            {
                "when": event.created_at,
                "title": event.event_name,
                "subtitle": event.payload.get("summary", "Evento de producto"),
                "actor": getattr(event.actor, "name", "Sistema") or getattr(event.actor, "email", "Sistema"),
                "source": "product",
                "source_label": "Producto",
                "source_color": "#F97316",
            }
        )
    timeline.sort(key=lambda item: item["when"], reverse=True)
    return timeline[:8]


def _format_currency(value: int | float | None) -> str:
    """Devuelve una moneda legible para el dashboard sin delegar formato al template."""
    return f"${intcomma(int(value or 0))}"


def _format_number(value: int | float | None) -> str:
    """Formatea enteros operacionales para tarjetas y tablas."""
    return intcomma(int(value or 0))


def _percentage(value: int | float, total: int | float) -> int:
    """Evita divisiones repetidas y centraliza porcentajes enteros del dashboard."""
    if not total:
        return 0
    return round((value / total) * 100)


def _decorate_bar_items(items: list[dict], *, value_key: str, label_key: str) -> list[dict]:
    """Añade ancho de barra, color y valores display a rankings reutilizados por la UI."""
    total = sum(int(item.get(value_key) or 0) for item in items)
    decorated = []
    for index, item in enumerate(items):
        raw_value = int(item.get(value_key) or 0)
        share_percent = _percentage(raw_value, total)
        decorated.append(
            {
                **item,
                "label": item.get(label_key) or "Sin dato",
                "value_display": _format_currency(raw_value),
                "bar_width": max(12, share_percent) if raw_value else 0,
                "share_percent": share_percent,
                "accent": BRAND_SERIES_COLORS[index % len(BRAND_SERIES_COLORS)],
            }
        )
    return decorated


def _build_focus_card(*, documents_due: int, maintenance_due: int, critical_alerts: int, tag_pending: int) -> dict:
    """Construye un donut simple con CSS para mostrar dónde está la presión operacional."""
    segments = [
        {"label": "Alertas críticas", "value": critical_alerts, "color": "#F97316"},
        {"label": "Docs por vencer", "value": documents_due, "color": "#1D2E53"},
        {"label": "Mantenciones", "value": maintenance_due, "color": "#5B7AB3"},
        {"label": "TAG observado", "value": tag_pending, "color": "#D6D8DB"},
    ]
    total = sum(segment["value"] for segment in segments)
    gradient_parts = []
    cursor = 0.0

    for segment in segments:
        angle = (segment["value"] / total) * 360 if total else 0
        end = cursor + angle
        segment["share_percent"] = _percentage(segment["value"], total)
        gradient_parts.append(f"{segment['color']} {cursor:.2f}deg {end:.2f}deg")
        cursor = end

    risk_load = (critical_alerts * 4) + (documents_due * 2) + (maintenance_due * 2) + (tag_pending * 3)
    health_score = max(0, 100 - min(risk_load, 100))

    return {
        "total": total,
        "total_display": _format_number(total),
        "score": health_score,
        "score_display": f"{health_score}%",
        "segments": segments,
        "gradient": f"conic-gradient({', '.join(gradient_parts)})" if total else "conic-gradient(#D6D8DB 0deg 360deg)",
    }


def dashboard_callback(request, context):
    """Inyecta KPIs y bloques resumidos a templates/admin/index.html."""
    filter_kwargs = _company_filter(request)
    month_start, month_end = _month_range()
    today = timezone.localdate()

    active_vehicles = Vehicle.objects.filter(status=Vehicle.STATUS_ACTIVE, **filter_kwargs)
    expiring_documents = _expiring_documents(filter_kwargs)
    due_maintenance = _due_maintenance(filter_kwargs)
    monthly_expenses = VehicleExpense.objects.filter(expense_date__range=(month_start, month_end), **filter_kwargs)
    critical_document_alerts = DocumentAlert.objects.filter(
        state=AlertState.PENDING,
        due_date__lte=today + timedelta(days=7),
        **filter_kwargs,
    )
    critical_maintenance_alerts = MaintenanceAlert.objects.filter(
        state=AlertState.PENDING,
        **filter_kwargs,
    )
    tag_snapshot = build_tag_snapshot(company_id=filter_kwargs.get("company_id"))
    active_vehicle_count = active_vehicles.count()
    documents_due_count = expiring_documents.count()
    maintenance_due_count = due_maintenance.count()
    monthly_expense_total = monthly_expenses.aggregate(total=Coalesce(Sum("amount_clp"), 0))["total"]
    critical_document_count = critical_document_alerts.count()
    critical_maintenance_count = critical_maintenance_alerts.count()
    critical_alert_total = critical_document_count + critical_maintenance_count
    tag_attention_count = tag_snapshot.pending_count + tag_snapshot.unmatched_count
    spend_by_category = _decorate_bar_items(
        _build_spend_by_category(filter_kwargs),
        value_key="total_amount",
        label_key="category__name",
    )
    top_expensive_vehicles = _decorate_bar_items(
        _build_top_expensive_vehicles(filter_kwargs),
        value_key="total_amount",
        label_key="vehicle__plate",
    )
    top_tag_vehicles = _decorate_bar_items(
        get_top_tag_vehicles(company_id=filter_kwargs.get("company_id"), limit=5),
        value_key="total_amount",
        label_key="vehicle__plate",
    )
    spend_per_vehicle = int(monthly_expense_total / active_vehicle_count) if active_vehicle_count else 0
    tag_reconciled_rate = _percentage(tag_snapshot.reconciled_total, tag_snapshot.month_total)
    focus_card = _build_focus_card(
        documents_due=documents_due_count,
        maintenance_due=maintenance_due_count,
        critical_alerts=critical_alert_total,
        tag_pending=tag_attention_count,
    )

    context.update(
        {
            "dashboard_kpis": {
                "active_vehicles": active_vehicle_count,
                "documents_due": documents_due_count,
                "maintenance_due": maintenance_due_count,
                "monthly_expense_total": monthly_expense_total,
                "critical_alerts": critical_alert_total,
                "tag_month_total": tag_snapshot.month_total,
            },
            "dashboard_kpi_cards": [
                {
                    "label": "Vehículos activos",
                    "value_display": _format_number(active_vehicle_count),
                    "note": "unidades operativas hoy",
                    "icon": "directions_car",
                    "tone": "navy",
                },
                {
                    "label": "Documentos por vencer",
                    "value_display": _format_number(documents_due_count),
                    "note": "próximos 30 días",
                    "icon": "description",
                    "tone": "blue",
                },
                {
                    "label": "Mantenimientos pendientes",
                    "value_display": _format_number(maintenance_due_count),
                    "note": "abiertos o cercanos",
                    "icon": "build_circle",
                    "tone": "slate",
                },
                {
                    "label": "Gasto del mes",
                    "value_display": _format_currency(monthly_expense_total),
                    "note": "egreso operativo acumulado",
                    "icon": "payments",
                    "tone": "orange",
                },
                {
                    "label": "Alertas críticas",
                    "value_display": _format_number(critical_alert_total),
                    "note": "requieren seguimiento inmediato",
                    "icon": "warning",
                    "tone": "alert",
                },
                {
                    "label": "TAG del mes",
                    "value_display": _format_currency(tag_snapshot.month_total),
                    "note": f"{tag_reconciled_rate}% conciliado",
                    "icon": "toll",
                    "tone": "navy-soft",
                },
            ],
            "dashboard_operational_highlights": [
                {
                    "label": "Gasto promedio por vehículo",
                    "value_display": _format_currency(spend_per_vehicle),
                    "note": "referencia del período actual",
                },
                {
                    "label": "Conciliación TAG",
                    "value_display": f"{tag_reconciled_rate}%",
                    "note": "monto conciliado del mes",
                },
                {
                    "label": "Alertas esta semana",
                    "value_display": _format_number(critical_alert_total),
                    "note": "prioridad alta en cola",
                },
            ],
            "dashboard_spend_by_category": spend_by_category,
            "dashboard_top_expensive_vehicles": top_expensive_vehicles,
            "dashboard_recent_documents": expiring_documents.order_by("expiry_date")[:8],
            "dashboard_due_maintenance": due_maintenance.order_by("next_due_date", "service_date")[:8],
            "dashboard_recent_activity": _build_recent_activity(filter_kwargs),
            "dashboard_focus_card": focus_card,
            "dashboard_tag_snapshot": tag_snapshot,
            "dashboard_recent_tag_movements": get_recent_tag_movements(company_id=filter_kwargs.get("company_id"), limit=6),
            "dashboard_top_tag_vehicles": top_tag_vehicles,
            "dashboard_tag_metrics": {
                "reconciled_rate": tag_reconciled_rate,
                "reconciled_rate_display": f"{tag_reconciled_rate}%",
                "attention_count": tag_attention_count,
                "attention_display": _format_number(tag_attention_count),
            },
            "dashboard_filters": {
                "month_label": month_start.strftime("%B %Y").capitalize(),
                "today": today,
                "window_end": today + timedelta(days=30),
            },
        }
    )
    return context
