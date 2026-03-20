"""Servicios del módulo de reportes para API, admin y futuras exportaciones."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.alerts.models import AlertState, DocumentAlert, MaintenanceAlert
from apps.documents.models import VehicleDocument
from apps.expenses.models import VehicleExpense
from apps.maintenance.models import MaintenanceRecord
from apps.reports.models import ReportExportLog
from apps.tags.models import TagCharge, TagTransit
from apps.vehicles.models import Vehicle


@dataclass
class ReportFilters:
    """Filtro normalizado que comparten las vistas API y admin."""

    company_id: int | None
    date_from: object
    date_to: object
    vehicle_id: int | None
    report_type: str
    status_focus: str


REPORT_TYPE_CHOICES = [
    ("all", "Vista general"),
    ("compliance", "Cumplimiento documental"),
    ("maintenance", "Mantenimiento"),
    ("expenses", "Gastos"),
    ("alerts", "Alertas"),
    ("tags", "TAG / Pórticos"),
]

REPORT_STATUS_CHOICES = [
    ("all", "Todos"),
    ("attention", "Requieren atención"),
    ("resolved", "Resueltos / conciliados"),
]


def build_report_filters(params, *, company_id: int | None) -> ReportFilters:
    """Parsea query params con defaults seguros para no romper el módulo."""
    today = timezone.localdate()
    date_from = parse_date(params.get("date_from") or "") or (today - timedelta(days=30))
    date_to = parse_date(params.get("date_to") or "") or today
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    try:
        vehicle_id = int(params.get("vehicle_id") or 0) or None
    except (TypeError, ValueError):
        vehicle_id = None

    report_type = params.get("report_type") or "all"
    valid_report_types = {value for value, _ in REPORT_TYPE_CHOICES}
    if report_type not in valid_report_types:
        report_type = "all"

    status_focus = params.get("status") or "all"
    valid_statuses = {value for value, _ in REPORT_STATUS_CHOICES}
    if status_focus not in valid_statuses:
        status_focus = "all"

    return ReportFilters(
        company_id=company_id,
        date_from=date_from,
        date_to=date_to,
        vehicle_id=vehicle_id,
        report_type=report_type,
        status_focus=status_focus,
    )


def _vehicle_scope(filters: ReportFilters):
    """Aplica scoping multiempresa y filtro opcional por vehículo."""
    qs = Vehicle.objects.all().order_by("plate")
    if filters.company_id is not None:
        qs = qs.filter(company_id=filters.company_id)
    if filters.vehicle_id:
        qs = qs.filter(id=filters.vehicle_id)
    return qs


def _document_scope(filters: ReportFilters):
    """Centraliza el queryset documental reutilizable para reportes."""
    qs = VehicleDocument.objects.filter(is_current=True).select_related("vehicle", "vehicle__assigned_driver")
    if filters.company_id is not None:
        qs = qs.filter(company_id=filters.company_id)
    if filters.vehicle_id:
        qs = qs.filter(vehicle_id=filters.vehicle_id)
    return qs


def _maintenance_scope(filters: ReportFilters):
    """Devuelve mantenciones ya scopeadas por tenant y vehículo."""
    qs = MaintenanceRecord.objects.select_related("vehicle")
    if filters.company_id is not None:
        qs = qs.filter(company_id=filters.company_id)
    if filters.vehicle_id:
        qs = qs.filter(vehicle_id=filters.vehicle_id)
    return qs


def _expense_scope(filters: ReportFilters):
    """Devuelve gastos scopeados para reutilizar breakdowns y KPIs."""
    qs = VehicleExpense.objects.select_related("vehicle", "category", "reported_by")
    if filters.company_id is not None:
        qs = qs.filter(company_id=filters.company_id)
    if filters.vehicle_id:
        qs = qs.filter(vehicle_id=filters.vehicle_id)
    return qs


def _alert_scopes(filters: ReportFilters):
    """Separa alertas de documentos y mantenciones para render simple en UI."""
    doc_qs = DocumentAlert.objects.select_related("vehicle_document", "driver_license").all()
    maintenance_qs = MaintenanceAlert.objects.select_related("vehicle").all()
    if filters.company_id is not None:
        doc_qs = doc_qs.filter(company_id=filters.company_id)
        maintenance_qs = maintenance_qs.filter(company_id=filters.company_id)
    if filters.vehicle_id:
        doc_qs = doc_qs.filter(vehicle_document__vehicle_id=filters.vehicle_id)
        maintenance_qs = maintenance_qs.filter(vehicle_id=filters.vehicle_id)
    return doc_qs, maintenance_qs


def _tag_scopes(filters: ReportFilters):
    """Encapsula scope de cobros y tránsitos TAG para el módulo de reportes."""
    charges = TagCharge.objects.select_related("vehicle", "road", "gate").all()
    transits = TagTransit.objects.select_related("vehicle", "road", "gate").all()
    if filters.company_id is not None:
        charges = charges.filter(company_id=filters.company_id)
        transits = transits.filter(company_id=filters.company_id)
    if filters.vehicle_id:
        charges = charges.filter(vehicle_id=filters.vehicle_id)
        transits = transits.filter(vehicle_id=filters.vehicle_id)
    return charges, transits


def build_dashboard_report(filters: ReportFilters) -> dict:
    """Mantiene la API existente pero sobre un servicio reutilizable."""
    today = timezone.localdate()
    maintenance_qs = _maintenance_scope(filters).filter(
        service_date__gte=filters.date_from,
        service_date__lte=filters.date_to,
    )
    document_qs = _document_scope(filters)

    upcoming_doc_expiries = document_qs.filter(
        expiry_date__gte=today,
        expiry_date__lte=today + timedelta(days=30),
    ).count()
    upcoming_7 = document_qs.filter(
        expiry_date__gte=today,
        expiry_date__lte=today + timedelta(days=7),
    ).count()
    upcoming_15 = document_qs.filter(
        expiry_date__gte=today,
        expiry_date__lte=today + timedelta(days=15),
    ).count()
    maintenance_due = _maintenance_scope(filters).filter(
        status=MaintenanceRecord.STATUS_OPEN,
        next_due_date__lte=today + timedelta(days=30),
    ).count()
    monthly_maintenance_cost = maintenance_qs.aggregate(total=Sum("cost_clp"))["total"] or 0
    top_vehicles = (
        maintenance_qs.values("vehicle_id", "vehicle__plate")
        .annotate(total_cost=Sum("cost_clp"), records=Count("id"))
        .order_by("-total_cost")[:5]
    )

    return {
        "date_from": str(filters.date_from),
        "date_to": str(filters.date_to),
        "upcoming_doc_expiries": upcoming_doc_expiries,
        "expiring_7d": upcoming_7,
        "expiring_15d": upcoming_15,
        "expiring_30d": upcoming_doc_expiries,
        "maintenance_due_30d": maintenance_due,
        "maintenance_cost_clp": monthly_maintenance_cost,
        "top_vehicles": list(top_vehicles),
    }


def build_vehicle_cost_rows(filters: ReportFilters) -> list[dict]:
    """Reutiliza el cálculo del reporte de costo por vehículo."""
    rows = []
    for vehicle in _vehicle_scope(filters).order_by("id"):
        total_cost = (
            MaintenanceRecord.objects.filter(
                company_id=vehicle.company_id,
                vehicle_id=vehicle.id,
            ).aggregate(total=Sum("cost_clp"))["total"]
            or 0
        )
        km = vehicle.current_km or 0
        cost_per_km = round(total_cost / km, 4) if km > 0 else None
        rows.append(
            {
                "vehicle_id": vehicle.id,
                "plate": vehicle.plate,
                "current_km": km,
                "total_cost_clp": total_cost,
                "cost_per_km": cost_per_km,
            }
        )
    return rows


def build_reports_admin_context(filters: ReportFilters) -> dict:
    """Arma el centro de reportes del admin con una sola pasada de servicios."""
    today = timezone.localdate()
    vehicle_options = list(
        _vehicle_scope(
            ReportFilters(
                company_id=filters.company_id,
                date_from=filters.date_from,
                date_to=filters.date_to,
                vehicle_id=None,
                report_type=filters.report_type,
                status_focus=filters.status_focus,
            )
        )
    )
    vehicles = list(_vehicle_scope(filters))
    documents = _document_scope(filters)
    maintenance = _maintenance_scope(filters)
    expenses = _expense_scope(filters).filter(expense_date__range=(filters.date_from, filters.date_to))
    document_alerts, maintenance_alerts = _alert_scopes(filters)
    tag_charges, tag_transits = _tag_scopes(filters)

    expiring_documents = documents.filter(
        expiry_date__gte=today,
        expiry_date__lte=today + timedelta(days=30),
    ).order_by("expiry_date", "vehicle__plate")
    expired_documents = documents.filter(expiry_date__lt=today).order_by("expiry_date", "vehicle__plate")
    maintenance_upcoming = maintenance.filter(status=MaintenanceRecord.STATUS_OPEN).filter(
        Q(next_due_date__isnull=False, next_due_date__lte=today + timedelta(days=30))
        | Q(next_due_km__isnull=False, next_due_km__lte=F("vehicle__current_km") + 500)
    )
    maintenance_overdue = maintenance.filter(status=MaintenanceRecord.STATUS_OPEN).filter(
        Q(next_due_date__lt=today) | Q(next_due_km__isnull=False, next_due_km__lte=F("vehicle__current_km"))
    )
    if filters.status_focus == "attention":
        document_alerts = document_alerts.exclude(state__in=[AlertState.ACKNOWLEDGED, AlertState.RESOLVED])
        maintenance_alerts = maintenance_alerts.exclude(state__in=[AlertState.ACKNOWLEDGED, AlertState.RESOLVED])
        expiring_documents = expiring_documents[:8]
        expired_documents = expired_documents[:8]
        maintenance_upcoming = maintenance_upcoming.order_by("next_due_date", "vehicle__plate")[:8]
        maintenance_overdue = maintenance_overdue.order_by("next_due_date", "vehicle__plate")[:8]
        expenses = expenses.filter(
            Q(approval_status=VehicleExpense.APPROVAL_REPORTED) | Q(payment_status=VehicleExpense.PAYMENT_UNPAID)
        )
        tag_charges = tag_charges.exclude(status=TagCharge.STATUS_RECONCILED)
    elif filters.status_focus == "resolved":
        document_alerts = document_alerts.filter(state__in=[AlertState.ACKNOWLEDGED, AlertState.RESOLVED, AlertState.SENT])
        maintenance_alerts = maintenance_alerts.filter(state__in=[AlertState.ACKNOWLEDGED, AlertState.RESOLVED, AlertState.SENT])
        expenses = expenses.filter(
            approval_status=VehicleExpense.APPROVAL_APPROVED,
            payment_status=VehicleExpense.PAYMENT_PAID,
        )
        tag_charges = tag_charges.filter(status=TagCharge.STATUS_RECONCILED)

    if filters.status_focus != "attention":
        maintenance_upcoming = maintenance_upcoming.order_by("next_due_date", "vehicle__plate")[:8]
        maintenance_overdue = maintenance_overdue.order_by("next_due_date", "vehicle__plate")[:8]
        expiring_documents = expiring_documents[:8]
        expired_documents = expired_documents[:8]

    recent_export_logs = ReportExportLog.objects.all().order_by("-created_at")
    if filters.company_id is not None:
        recent_export_logs = recent_export_logs.filter(company_id=filters.company_id)

    expense_by_category = list(
        expenses.values("category__name")
        .annotate(total_amount=Coalesce(Sum("amount_clp"), 0), total_items=Count("id"))
        .order_by("-total_amount", "category__name")[:6]
    )
    expense_by_vehicle = list(
        expenses.values("vehicle__plate")
        .annotate(total_amount=Coalesce(Sum("amount_clp"), 0), total_items=Count("id"))
        .order_by("-total_amount", "vehicle__plate")[:6]
    )
    alert_summary = {
        "documents_pending": document_alerts.filter(state=AlertState.PENDING).count(),
        "documents_sent": document_alerts.filter(state=AlertState.SENT).count(),
        "maintenance_pending": maintenance_alerts.filter(state=AlertState.PENDING).count(),
        "maintenance_sent": maintenance_alerts.filter(state=AlertState.SENT).count(),
    }
    tag_summary = {
        "total_amount": tag_charges.filter(charge_date__range=(filters.date_from, filters.date_to)).aggregate(total=Coalesce(Sum("amount_clp"), 0))["total"],
        "pending_count": tag_charges.filter(status=TagCharge.STATUS_PENDING).count(),
        "unmatched_count": tag_charges.filter(status=TagCharge.STATUS_UNMATCHED).count(),
        "recent_transits": tag_transits.order_by("-transit_at")[:6],
        "top_vehicles": list(
            tag_charges.filter(charge_date__range=(filters.date_from, filters.date_to))
            .values("vehicle__plate")
            .annotate(total_amount=Coalesce(Sum("amount_clp"), 0), total_items=Count("id"))
            .order_by("-total_amount", "vehicle__plate")[:6]
        ),
    }

    kpis = {
        "vehicles": len(vehicles),
        "expiring_documents": documents.filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=30),
        ).count(),
        "expired_documents": documents.filter(expiry_date__lt=today).count(),
        "open_maintenance": maintenance.filter(status=MaintenanceRecord.STATUS_OPEN).count(),
        "expenses_total": expenses.aggregate(total=Coalesce(Sum("amount_clp"), 0))["total"],
        "active_alerts": alert_summary["documents_pending"] + alert_summary["maintenance_pending"],
        "tag_total": tag_summary["total_amount"],
    }

    return {
        "report_filters": filters,
        "report_type_choices": REPORT_TYPE_CHOICES,
        "report_status_choices": REPORT_STATUS_CHOICES,
        "report_vehicles": vehicle_options,
        "report_kpis": kpis,
        "report_expiring_documents": expiring_documents,
        "report_expired_documents": expired_documents,
        "report_maintenance_upcoming": maintenance_upcoming,
        "report_maintenance_overdue": maintenance_overdue,
        "report_expense_by_category": expense_by_category,
        "report_expense_by_vehicle": expense_by_vehicle,
        "report_alert_summary": alert_summary,
        "report_tag_summary": tag_summary,
        "report_recent_exports": recent_export_logs[:8],
    }
