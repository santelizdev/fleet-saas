"""Infraestructura liviana para registrar auditoría con contexto de request."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from django.db import models

from .models import AuditLog

_current_request: ContextVar = ContextVar("audit_current_request", default=None)


def set_current_request(request):
    return _current_request.set(request)


def reset_current_request(token) -> None:
    _current_request.reset(token)


def get_current_request():
    return _current_request.get()


@contextmanager
def audit_request_context(request):
    token = set_current_request(request)
    try:
        yield
    finally:
        reset_current_request(token)


def _normalize_value(value):
    if isinstance(value, models.Model):
        return value.pk
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value == int(value) else float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def serialize_instance_fields(instance: models.Model, field_names: tuple[str, ...]) -> dict:
    data: dict[str, object] = {}
    for field_name in field_names:
        try:
            value = getattr(instance, field_name)
        except Exception:
            continue
        data[field_name] = _normalize_value(value)
    return data


def build_object_summary(instance: models.Model) -> str:
    for attr in ("plate", "name", "email", "license_number", "source_name", "code"):
        value = getattr(instance, attr, None)
        if value:
            return str(value)
    return str(getattr(instance, "pk", "")) or instance._meta.verbose_name.title()


def _request_meta(request):
    if request is None:
        return "", None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    remote_addr = (forwarded.split(",")[0].strip() if forwarded else "") or request.META.get("REMOTE_ADDR")
    return getattr(request, "request_id", "") or "", remote_addr or None


def log_audit_event(
    *,
    action: str,
    object_type: str,
    object_id: str,
    company_id: int | None = None,
    actor_id: int | None = None,
    source: str | None = None,
    status: str = AuditLog.STATUS_INFO,
    summary: str = "",
    metadata: dict | None = None,
    before: dict | None = None,
    after: dict | None = None,
    request=None,
) -> AuditLog:
    request = request or get_current_request()

    if request is not None:
        user = getattr(request, "user", None)
        if actor_id is None and getattr(user, "is_authenticated", False):
            actor_id = user.id
        if company_id is None:
            company_id = getattr(request, "company_id", None)
            if company_id is None and getattr(user, "is_authenticated", False):
                company_id = getattr(user, "company_id", None)
        if source is None:
            if request.path.startswith("/admin/"):
                source = AuditLog.SOURCE_ADMIN
            elif request.path.startswith("/api/"):
                source = AuditLog.SOURCE_API
            else:
                source = AuditLog.SOURCE_SYSTEM

    request_id, remote_addr = _request_meta(request)
    return AuditLog.objects.create(
        company_id=company_id,
        actor_id=actor_id,
        source=source or AuditLog.SOURCE_SYSTEM,
        status=status,
        action=action,
        summary=summary[:255],
        object_type=object_type,
        object_id=str(object_id),
        metadata_json=metadata,
        before_json=before,
        after_json=after,
        request_id=request_id,
        remote_addr=remote_addr,
    )
