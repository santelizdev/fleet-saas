"""Servicios de consulta para dashboard TAG y vista 360 de vehículo."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.companies.models import Company
from apps.vehicles.models import Vehicle

from .models import TagCharge, TagImportBatch, TagTransit, TollGate, TollRoad


@dataclass(frozen=True)
class TagKpiSnapshot:
    month_total: int
    reconciled_total: int
    pending_count: int
    unmatched_count: int


@dataclass(frozen=True)
class TagCsvImportResult:
    batch: TagImportBatch
    created_transits: int
    created_charges: int
    matched_items: int
    unmatched_items: int
    duplicate_count: int
    error_count: int
    error_samples: tuple[str, ...]


def current_month_range() -> tuple[date, date]:
    """Devuelve el rango mensual corriente para filtros rápidos."""
    today = timezone.localdate()
    start = today.replace(day=1)
    next_month = (start + timedelta(days=32)).replace(day=1)
    end = next_month - timedelta(days=1)
    return start, end


def month_range_from_value(month_value: str | None) -> tuple[date, date, str]:
    """Convierte YYYY-MM a rango inclusivo. Si no viene, usa el mes actual."""
    if month_value:
        try:
            start = datetime.strptime(month_value, "%Y-%m").date().replace(day=1)
        except ValueError:
            start, end = current_month_range()
            return start, end, start.strftime("%Y-%m")
        next_month = (start + timedelta(days=32)).replace(day=1)
        return start, next_month - timedelta(days=1), start.strftime("%Y-%m")
    start, end = current_month_range()
    return start, end, start.strftime("%Y-%m")


def normalize_plate(value: str) -> str:
    """Normaliza patente para matching simple entre CSV y maestro de vehículos."""
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def parse_amount_clp(raw_value: str) -> int:
    """Convierte montos estilo 413,02 a entero CLP redondeado."""
    clean = (raw_value or "").strip().replace(".", "").replace(",", ".")
    if not clean:
        return 0
    try:
        amount = Decimal(clean)
    except InvalidOperation as exc:
        raise ValueError(f"Importe inválido: {raw_value}") from exc
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_csv_transit_at(raw_value: str) -> datetime:
    """Parsea fecha/hora del CSV manual de autopista."""
    try:
        parsed = datetime.strptime(raw_value.strip(), "%d/%m/%Y %H:%M:%S")
    except ValueError as exc:
        raise ValueError(f"FechaHora inválida: {raw_value}") from exc
    return timezone.make_aware(parsed, timezone.get_current_timezone())


def import_manual_tag_csv(
    *,
    company: Company,
    vehicle: Vehicle,
    uploaded_file,
    source_name: str,
    created_by,
) -> TagCsvImportResult:
    """Importa CSV manual de autopista y genera transits/cobros operativos."""
    if vehicle.company_id != company.id:
        raise ValueError("El vehículo seleccionado no pertenece a la empresa elegida.")

    raw_content = uploaded_file.read()
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    text_file = io.StringIO(raw_content.decode("utf-8-sig"))
    reader = csv.DictReader(text_file, delimiter=";", quotechar='"')
    expected_headers = {"Patente", "FechaHora", "Portico", "Concesionaria", "TAG", "Horario", "Importe", "Factura"}
    if not reader.fieldnames or set(reader.fieldnames) != expected_headers:
        raise ValueError("El CSV no tiene el formato esperado del detalle de autopista.")

    rows = [row for row in reader if row and any((value or "").strip() for value in row.values())]
    expected_plate = normalize_plate(vehicle.plate)
    mismatched_plates = sorted(
        {
            normalize_plate(row["Patente"])
            for row in rows
            if normalize_plate(row["Patente"]) and normalize_plate(row["Patente"]) != expected_plate
        }
    )
    if mismatched_plates:
        readable = ", ".join(mismatched_plates[:5])
        raise ValueError(
            f"El CSV no coincide con el vehículo seleccionado ({vehicle.plate}). "
            f"Se encontraron patentes distintas: {readable}."
        )

    road_cache: dict[str, TollRoad] = {}
    gate_cache: dict[tuple[int, str], TollGate] = {}
    period_dates: list[date] = []
    created_transits = 0
    created_charges = 0
    matched_items = 0
    unmatched_items = 0
    duplicate_count = 0
    errors: list[str] = []
    total_rows = len(rows)
    seen_rows: set[tuple[str, str, str, int, str, str]] = set()

    with transaction.atomic():
        batch = TagImportBatch.objects.create(
            company=company,
            source_name=source_name or "Carga manual CSV",
            source_file_name=getattr(uploaded_file, "name", ""),
            created_by=created_by,
            status=TagImportBatch.STATUS_PENDING,
        )

        for row_number, row in enumerate(rows, start=2):
            try:
                plate = expected_plate
                transit_at = parse_csv_transit_at(row["FechaHora"])
                transit_date = transit_at.date()
                is_weekend = transit_at.weekday() >= 5
                amount_clp = parse_amount_clp(row["Importe"])
                road_code = (row["Concesionaria"] or "").strip() or "SIN_CONCESION"
                gate_code = (row["Portico"] or "").strip() or "SIN_PORTICO"
                tag_reference = (row["TAG"] or "").strip()
                schedule_code = (row["Horario"] or "").strip()
                invoice_reference = (row["Factura"] or "").strip()
                row_fingerprint = (
                    plate,
                    transit_at.isoformat(),
                    gate_code,
                    amount_clp,
                    tag_reference,
                    invoice_reference,
                )

                if row_fingerprint in seen_rows:
                    duplicate_count += 1
                    continue
                seen_rows.add(row_fingerprint)

                road = road_cache.get(road_code)
                if road is None:
                    road, _ = TollRoad.objects.get_or_create(
                        company=company,
                        name=road_code,
                        defaults={"code": road_code, "operator_name": road_code, "is_active": True},
                    )
                    road_cache[road_code] = road

                gate_key = (road.id, gate_code)
                gate = gate_cache.get(gate_key)
                if gate is None:
                    gate, _ = TollGate.objects.get_or_create(
                        company=company,
                        road=road,
                        code=gate_code,
                        defaults={"name": gate_code, "is_active": True},
                    )
                    gate_cache[gate_key] = gate

                if TagCharge.objects.filter(
                    company=company,
                    vehicle=vehicle,
                    detected_plate=plate,
                    billed_at=transit_at,
                    gate=gate,
                    amount_clp=amount_clp,
                    tag_reference=tag_reference,
                    invoice_reference=invoice_reference,
                ).exists():
                    duplicate_count += 1
                    continue

                transit_status = TagTransit.MATCH_MATCHED
                charge_status = TagCharge.STATUS_RECONCILED

                transit = TagTransit.objects.create(
                    company=company,
                    batch=batch,
                    road=road,
                    gate=gate,
                    vehicle=vehicle,
                    detected_plate=plate,
                    tag_reference=tag_reference,
                    schedule_code=schedule_code,
                    invoice_reference=invoice_reference,
                    transit_at=transit_at,
                    transit_date=transit_date,
                    is_weekend=is_weekend,
                    amount_clp=amount_clp,
                    match_status=transit_status,
                )
                TagCharge.objects.create(
                    company=company,
                    transit=transit,
                    batch=batch,
                    road=road,
                    gate=gate,
                    vehicle=vehicle,
                    detected_plate=plate,
                    tag_reference=tag_reference,
                    schedule_code=schedule_code,
                    invoice_reference=invoice_reference,
                    charge_date=transit_date,
                    billed_at=transit_at,
                    is_weekend=is_weekend,
                    amount_clp=amount_clp,
                    status=charge_status,
                )
                period_dates.append(transit_date)
                created_transits += 1
                created_charges += 1
                matched_items += 1
            except Exception as exc:  # noqa: BLE001 - resumen controlado para carga manual
                errors.append(f"Fila {row_number}: {exc}")

        batch.total_rows = total_rows
        if period_dates:
            batch.period_start = min(period_dates)
            batch.period_end = max(period_dates)
        batch.status = TagImportBatch.STATUS_FAILED if errors and not created_charges else TagImportBatch.STATUS_PROCESSED
        batch.notes = (
            f"Filas: {total_rows}. Importadas: {created_charges}. "
            f"Conciliadas: {matched_items}. Duplicadas: {duplicate_count}. Errores: {len(errors)}."
        )
        if errors:
            batch.notes = f"{batch.notes}\n" + "\n".join(errors[:5])
        batch.save(update_fields=["total_rows", "period_start", "period_end", "status", "notes"])

    return TagCsvImportResult(
        batch=batch,
        created_transits=created_transits,
        created_charges=created_charges,
        matched_items=matched_items,
        unmatched_items=unmatched_items,
        duplicate_count=duplicate_count,
        error_count=len(errors),
        error_samples=tuple(errors[:5]),
    )


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
