from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.companies.models import CompanyLimit
from apps.documents.models import Attachment
from apps.reports.models import ReportExportLog
from apps.vehicles.models import Vehicle


@dataclass
class EffectiveLimits:
    max_vehicles: int
    max_users: int
    max_storage_mb: int
    max_uploads_per_day: int
    max_exports_per_day: int


def get_effective_limits(company_id: int) -> EffectiveLimits:
    defaults = EffectiveLimits(
        max_vehicles=int(getattr(settings, "DEFAULT_MAX_VEHICLES", 100)),
        max_users=int(getattr(settings, "DEFAULT_MAX_USERS", 50)),
        max_storage_mb=int(getattr(settings, "DEFAULT_MAX_STORAGE_MB", 1024)),
        max_uploads_per_day=int(getattr(settings, "DEFAULT_MAX_UPLOADS_PER_DAY", 200)),
        max_exports_per_day=int(getattr(settings, "DEFAULT_MAX_EXPORTS_PER_DAY", 20)),
    )

    limits = CompanyLimit.objects.filter(company_id=company_id).first()
    if not limits:
        return defaults

    return EffectiveLimits(
        max_vehicles=limits.max_vehicles,
        max_users=limits.max_users,
        max_storage_mb=limits.max_storage_mb,
        max_uploads_per_day=limits.max_uploads_per_day,
        max_exports_per_day=limits.max_exports_per_day,
    )


def _audit_limit_breach(company_id: int, actor_id: int | None, action: str, details: dict):
    AuditLog.objects.create(
        company_id=company_id,
        actor_id=actor_id,
        action=action,
        object_type="CompanyLimit",
        object_id=str(company_id),
        before_json=None,
        after_json=details,
    )


def enforce_upload_limits(
    *,
    company_id: int,
    actor_id: int | None = None,
    incoming_size_bytes: int = 0,
    replacing_size_bytes: int = 0,
):
    limits = get_effective_limits(company_id)
    today = timezone.localdate()

    uploads_today = Attachment.objects.filter(company_id=company_id, created_at__date=today).count()
    if uploads_today >= limits.max_uploads_per_day:
        _audit_limit_breach(
            company_id,
            actor_id,
            "limit.uploads.exceeded",
            {"uploads_today": uploads_today, "max_uploads_per_day": limits.max_uploads_per_day},
        )
        raise PermissionDenied("Límite diario de uploads excedido para tu plan.")

    used_bytes = Attachment.objects.filter(company_id=company_id).aggregate(total=Sum("size_bytes"))["total"] or 0
    projected_bytes = max(used_bytes - replacing_size_bytes, 0) + incoming_size_bytes
    used_mb = projected_bytes / (1024 * 1024)
    if used_mb >= limits.max_storage_mb:
        _audit_limit_breach(
            company_id,
            actor_id,
            "limit.storage.exceeded",
            {
                "used_mb": round(used_mb, 2),
                "max_storage_mb": limits.max_storage_mb,
                "incoming_size_bytes": incoming_size_bytes,
                "replacing_size_bytes": replacing_size_bytes,
            },
        )
        raise PermissionDenied("Límite de almacenamiento excedido para tu plan.")


def enforce_export_limits(*, company_id: int, actor_id: int | None = None):
    limits = get_effective_limits(company_id)
    today = timezone.localdate()
    exports_today = ReportExportLog.objects.filter(company_id=company_id, created_at__date=today).count()
    if exports_today >= limits.max_exports_per_day:
        _audit_limit_breach(
            company_id,
            actor_id,
            "limit.exports.exceeded",
            {"exports_today": exports_today, "max_exports_per_day": limits.max_exports_per_day},
        )
        raise PermissionDenied("Límite diario de exports excedido para tu plan.")


def enforce_vehicle_limit(*, company_id: int, actor_id: int | None = None, new_units: int = 1):
    limits = get_effective_limits(company_id)
    current = Vehicle.objects.filter(company_id=company_id).count()
    if current + new_units > limits.max_vehicles:
        _audit_limit_breach(
            company_id,
            actor_id,
            "limit.vehicles.exceeded",
            {"current_vehicles": current, "new_units": new_units, "max_vehicles": limits.max_vehicles},
        )
        raise PermissionDenied("Límite de vehículos excedido para tu plan.")
