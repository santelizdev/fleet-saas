"""Captura automática de eventos de auditoría relevantes para operación y revisión."""

from __future__ import annotations

from django.apps import apps
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

from .models import AuditLog
from .services import build_object_summary, get_current_request, log_audit_event, serialize_instance_fields


def _model_registry():
    return {
        apps.get_model("companies", "Company"): ("name", "rut", "status"),
        apps.get_model("companies", "Branch"): ("company", "name", "code", "address"),
        apps.get_model("companies", "CompanyLimit"): ("company", "max_vehicles", "max_users", "max_storage_mb", "max_exports_per_day"),
        apps.get_model("accounts", "User"): ("email", "name", "phone", "company", "is_active", "is_staff", "is_superuser"),
        apps.get_model("accounts", "Role"): ("company", "name", "description"),
        apps.get_model("vehicles", "Vehicle"): ("company", "branch", "plate", "brand", "model", "year", "current_km", "status", "assigned_driver"),
        apps.get_model("documents", "VehicleDocument"): ("company", "vehicle", "type", "status", "is_current", "issue_date", "expiry_date"),
        apps.get_model("documents", "DriverLicense"): ("company", "driver", "license_number", "category", "status", "is_current", "issue_date", "expiry_date"),
        apps.get_model("maintenance", "MaintenanceRecord"): ("company", "vehicle", "type", "status", "service_date", "odometer_km", "cost_clp", "next_due_date", "next_due_km"),
        apps.get_model("expenses", "ExpenseCategory"): ("company", "name"),
        apps.get_model("expenses", "VehicleExpense"): ("company", "vehicle", "category", "amount_clp", "expense_date", "approval_status", "payment_status", "reported_by", "approved_by", "paid_by"),
        apps.get_model("tags", "TagImportBatch"): ("company", "source_name", "source_file_name", "status", "total_rows", "period_start", "period_end"),
    }


AUDITED_MODELS = None


def get_audited_fields(model_cls):
    global AUDITED_MODELS
    if AUDITED_MODELS is None:
        AUDITED_MODELS = _model_registry()
    return AUDITED_MODELS.get(model_cls)


@receiver(user_logged_in)
def audit_user_logged_in(sender, request, user, **kwargs):
    log_audit_event(
        request=request,
        company_id=getattr(user, "company_id", None),
        actor_id=user.id,
        source=AuditLog.SOURCE_AUTH,
        status=AuditLog.STATUS_SUCCESS,
        action="auth.login",
        object_type="User",
        object_id=user.id,
        summary=f"Inicio de sesión de {user.email}",
        metadata={"email": user.email},
    )


@receiver(user_logged_out)
def audit_user_logged_out(sender, request, user, **kwargs):
    if user is None:
        return
    log_audit_event(
        request=request,
        company_id=getattr(user, "company_id", None),
        actor_id=getattr(user, "id", None),
        source=AuditLog.SOURCE_AUTH,
        status=AuditLog.STATUS_INFO,
        action="auth.logout",
        object_type="User",
        object_id=getattr(user, "id", "anonymous"),
        summary=f"Cierre de sesión de {getattr(user, 'email', 'usuario')}",
        metadata={"email": getattr(user, "email", "")},
    )


@receiver(user_login_failed)
def audit_user_login_failed(sender, credentials, request, **kwargs):
    identifier = credentials.get("username") or credentials.get("email") or "unknown"
    log_audit_event(
        request=request,
        source=AuditLog.SOURCE_AUTH,
        status=AuditLog.STATUS_FAILED,
        action="auth.login_failed",
        object_type="User",
        object_id=identifier,
        summary=f"Login fallido para {identifier}",
        metadata={"identifier": identifier},
    )


@receiver(pre_save)
def audit_capture_before(sender, instance, raw=False, **kwargs):
    if raw:
        return
    fields = get_audited_fields(sender)
    if not fields or not getattr(instance, "pk", None):
        return
    previous = sender._default_manager.filter(pk=instance.pk).first()
    if previous is None:
        return
    instance._audit_before_snapshot = serialize_instance_fields(previous, fields)


@receiver(post_save)
def audit_model_save(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    fields = get_audited_fields(sender)
    if not fields:
        return
    action_suffix = "create" if created else "update"
    after = serialize_instance_fields(instance, fields)
    before = None if created else getattr(instance, "_audit_before_snapshot", None)
    if not created and before == after:
        return
    log_audit_event(
        request=get_current_request(),
        company_id=getattr(instance, "company_id", None),
        action=f"{instance._meta.app_label}.{instance._meta.model_name}.{action_suffix}",
        object_type=sender.__name__,
        object_id=instance.pk,
        status=AuditLog.STATUS_SUCCESS,
        summary=f"{sender._meta.verbose_name.title()} {build_object_summary(instance)} {'creado' if created else 'actualizado'}",
        before=before,
        after=after,
    )


@receiver(pre_delete)
def audit_model_delete(sender, instance, **kwargs):
    fields = get_audited_fields(sender)
    if not fields:
        return
    before = serialize_instance_fields(instance, fields)
    log_audit_event(
        request=get_current_request(),
        company_id=getattr(instance, "company_id", None),
        action=f"{instance._meta.app_label}.{instance._meta.model_name}.delete",
        object_type=sender.__name__,
        object_id=instance.pk,
        status=AuditLog.STATUS_WARNING,
        summary=f"{sender._meta.verbose_name.title()} {build_object_summary(instance)} eliminado",
        before=before,
    )
