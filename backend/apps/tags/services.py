"""Servicios de consulta para dashboard TAG y vista 360 de vehículo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import TagCharge, TagTransit


@dataclass(frozen=True)
class TagKpiSnapshot:
    month_total: int
    reconciled_total: int
    pending_count: int
    unmatched_count: int


def current_month_range() -> tuple[date, date]:
    """Devuelve el rango mensual corriente para filtros rápidos."""
    today = timezone.localdate()
    start = today.replace(day=1)
    next_month = (start + timedelta(days=32)).replace(day=1)
    end = next_month - timedelta(days=1)
    return start, end


def build_tag_snapshot(*, company_id: int | None = None) -> TagKpiSnapshot:
    """Resume los principales indicadores de cobros TAG del período actual."""
    month_start, month_end = current_month_range()
    charges = TagCharge.objects.filter(charge_date__range=(month_start, month_end))
    if company_id:
        charges = charges.filter(company_id=company_id)

    aggregated = charges.aggregate(month_total=Coalesce(Sum("amount_clp"), 0))
    reconciled_amount = charges.filter(status=TagCharge.STATUS_RECONCILED).aggregate(
        total=Coalesce(Sum("amount_clp"), 0)
    )["total"]
    return TagKpiSnapshot(
        month_total=aggregated["month_total"],
        reconciled_total=reconciled_amount,
        pending_count=charges.filter(status=TagCharge.STATUS_PENDING).count(),
        unmatched_count=charges.filter(status=TagCharge.STATUS_UNMATCHED).count(),
    )


def get_recent_tag_movements(*, company_id: int | None = None, vehicle_id: int | None = None, limit: int = 8):
    """Obtiene movimientos recientes para dashboard y ficha 360."""
    transits = TagTransit.objects.select_related("road", "gate", "vehicle").order_by("-transit_at")
    if company_id:
        transits = transits.filter(company_id=company_id)
    if vehicle_id:
        transits = transits.filter(vehicle_id=vehicle_id)
    return list(transits[:limit])


def get_top_tag_vehicles(*, company_id: int | None = None, limit: int = 5):
    """Devuelve vehículos con mayor gasto TAG del mes."""
    month_start, month_end = current_month_range()
    charges = TagCharge.objects.filter(charge_date__range=(month_start, month_end), vehicle__isnull=False)
    if company_id:
        charges = charges.filter(company_id=company_id)
    return list(
        charges.values("vehicle_id", "vehicle__plate")
        .annotate(total_amount=Coalesce(Sum("amount_clp"), 0), total_charges=Count("id"))
        .order_by("-total_amount", "vehicle__plate")[:limit]
    )
