"""Servicios para la vista 360 de vehículos dentro del admin."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from apps.alerts.models import DocumentAlert, MaintenanceAlert
from apps.documents.models import VehicleDocument
from apps.expenses.models import VehicleExpense
from apps.maintenance.models import MaintenanceRecord, VehicleOdometerLog
from apps.tags.models import TagCharge
from apps.tags.services import get_recent_tag_movements

from .models import Vehicle


@dataclass(frozen=True)
class VehicleRiskSummary:
    """Resume criticidad documental y operacional del vehículo."""

    label: str
    tone: str
    reason: str


def build_vehicle_overview(*, vehicle: Vehicle) -> dict:
    """Agrupa toda la información operacional importante en una sola estructura."""
    today = timezone.localdate()
    documents = list(
        vehicle.documents.select_related("created_by").filter(is_current=True).order_by("expiry_date")[:6]
    )
    maintenance = list(
        vehicle.maintenance_records.select_related("created_by").order_by("-service_date")[:6]
    )
    upcoming_maintenance = list(
        vehicle.maintenance_records.filter(next_due_date__isnull=False).order_by("next_due_date")[:4]
    )
    odometer_logs = list(vehicle.odometer_logs.select_related("recorded_by").order_by("-created_at")[:5])
    recent_expenses = list(
        vehicle.expenses.select_related("category", "reported_by").order_by("-expense_date", "-id")[:6]
    )
    document_alerts = DocumentAlert.objects.filter(vehicle_document__vehicle=vehicle).order_by("-created_at")[:6]
    maintenance_alerts = MaintenanceAlert.objects.filter(vehicle=vehicle).order_by("-created_at")[:6]
    tag_charges = TagCharge.objects.select_related("road", "gate").filter(vehicle=vehicle).order_by("-charge_date", "-id")
    total_expense = vehicle.expenses.aggregate(total=Coalesce(Sum("amount_clp"), 0))["total"]
    total_tag_expense = tag_charges.aggregate(total=Coalesce(Sum("amount_clp"), 0))["total"]
    monthly_expense = vehicle.expenses.filter(expense_date__gte=today.replace(day=1)).aggregate(
        total=Coalesce(Sum("amount_clp"), 0)
    )["total"]
    monthly_tag_expense = tag_charges.filter(charge_date__gte=today.replace(day=1)).aggregate(
        total=Coalesce(Sum("amount_clp"), 0)
    )["total"]

    risk = _build_vehicle_risk(vehicle=vehicle, documents=documents, upcoming_maintenance=upcoming_maintenance)

    quick_links = {
        "documents": f"{reverse('admin:documents_vehicledocument_changelist')}?vehicle__id__exact={vehicle.id}",
        "maintenance": f"{reverse('admin:maintenance_maintenancerecord_changelist')}?vehicle__id__exact={vehicle.id}",
        "expenses": f"{reverse('admin:expenses_vehicleexpense_changelist')}?vehicle__id__exact={vehicle.id}",
        "alerts": f"{reverse('admin:alerts_maintenancealert_changelist')}?vehicle__id__exact={vehicle.id}",
        "tag": f"{reverse('admin:tags_tagcharge_changelist')}?vehicle__id__exact={vehicle.id}",
    }

    return {
        "vehicle": vehicle,
        "risk": risk,
        "documents": documents,
        "maintenance": maintenance,
        "upcoming_maintenance": upcoming_maintenance,
        "odometer_logs": odometer_logs,
        "recent_expenses": recent_expenses,
        "document_alerts": list(document_alerts),
        "maintenance_alerts": list(maintenance_alerts),
        "recent_tag_charges": list(tag_charges[:6]),
        "recent_tag_movements": get_recent_tag_movements(company_id=vehicle.company_id, vehicle_id=vehicle.id, limit=6),
        "driver": vehicle.assigned_driver,
        "quick_links": quick_links,
        "metrics": {
            "document_count": len(documents),
            "maintenance_count": MaintenanceRecord.objects.filter(vehicle=vehicle).count(),
            "expense_count": VehicleExpense.objects.filter(vehicle=vehicle).count(),
            "alert_count": document_alerts.count() + maintenance_alerts.count(),
            "total_expense": total_expense,
            "monthly_expense": monthly_expense,
            "total_tag_expense": total_tag_expense,
            "monthly_tag_expense": monthly_tag_expense,
            "current_km": vehicle.current_km,
            "last_odometer": odometer_logs[0].km if odometer_logs else vehicle.current_km,
        },
    }


def _build_vehicle_risk(*, vehicle: Vehicle, documents: list[VehicleDocument], upcoming_maintenance: list[MaintenanceRecord]) -> VehicleRiskSummary:
    """Determina un badge simple de riesgo para la cabecera 360."""
    today = timezone.localdate()
    document_due_soon = any(doc.expiry_date <= today + timedelta(days=15) for doc in documents)
    document_expired = any(doc.expiry_date < today for doc in documents)
    maintenance_due_soon = any(record.next_due_date and record.next_due_date <= today + timedelta(days=15) for record in upcoming_maintenance)

    if vehicle.status != Vehicle.STATUS_ACTIVE or document_expired:
        return VehicleRiskSummary(label="Crítico", tone="danger", reason="Vehículo inactivo o documento vencido")
    if document_due_soon or maintenance_due_soon:
        return VehicleRiskSummary(label="Atención", tone="warning", reason="Tiene vencimientos o mantenciones próximas")
    return VehicleRiskSummary(label="Controlado", tone="success", reason="Sin riesgos inmediatos detectados")
