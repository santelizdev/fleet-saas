"""Configuración compartida del admin Unfold y helpers de navegación."""

from __future__ import annotations

from typing import Any

from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.alerts.models import AlertState, DocumentAlert, MaintenanceAlert


def environment_callback(request) -> list[str]:
    """Muestra un badge simple según el entorno activo del backoffice."""
    color = "success" if not request.META.get("HTTP_HOST", "").startswith("localhost") else "info"
    return [timezone.now().strftime("%Y-%m-%d"), color]


def _critical_alert_count(request) -> int:
    """Resume alertas pendientes/sin resolver visibles para el usuario actual."""
    if not request.user.is_authenticated:
        return 0

    base_doc = DocumentAlert.objects.exclude(state__in=[AlertState.RESOLVED, AlertState.ACKNOWLEDGED])
    base_maintenance = MaintenanceAlert.objects.exclude(state__in=[AlertState.RESOLVED, AlertState.ACKNOWLEDGED])

    if not request.user.is_superuser:
        base_doc = base_doc.filter(company_id=request.user.company_id)
        base_maintenance = base_maintenance.filter(company_id=request.user.company_id)

    return base_doc.count() + base_maintenance.count()


def navigation(request) -> list[dict[str, Any]]:
    """Agrupa el menú lateral del admin por dominios operacionales."""
    alert_count = _critical_alert_count(request)

    return [
        {
            "title": _("Resumen"),
            "separator": True,
            "items": [
                {
                    "title": _("Dashboard"),
                    "icon": "dashboard",
                    "link": reverse_lazy("admin:index"),
                },
            ],
        },
        {
            "title": _("Flota"),
            "items": [
                {
                    "title": _("Vehículos"),
                    "icon": "directions_car",
                    "link": reverse_lazy("admin:vehicles_vehicle_changelist"),
                },
                {
                    "title": _("Odómetro"),
                    "icon": "speed",
                    "link": reverse_lazy("admin:maintenance_vehicleodometerlog_changelist"),
                },
                {
                    "title": _("Conductores"),
                    "icon": "badge",
                    "link": reverse_lazy("admin:accounts_driver_changelist"),
                },
            ],
        },
        {
            "title": _("Documentos"),
            "items": [
                {
                    "title": _("Documentos vehículo"),
                    "icon": "description",
                    "link": reverse_lazy("admin:documents_vehicledocument_changelist"),
                },
                {
                    "title": _("Licencias"),
                    "icon": "article",
                    "link": reverse_lazy("admin:documents_driverlicense_changelist"),
                },
            ],
        },
        {
            "title": _("Mantenimientos"),
            "items": [
                {
                    "title": _("Plan mantenimiento"),
                    "icon": "build",
                    "link": reverse_lazy("admin:maintenance_maintenancerecord_changelist"),
                },
            ],
        },
        {
            "title": _("Gastos"),
            "items": [
                {
                    "title": _("Gastos de flota"),
                    "icon": "payments",
                    "link": reverse_lazy("admin:expenses_vehicleexpense_changelist"),
                },
                {
                    "title": _("Categorías"),
                    "icon": "category",
                    "link": reverse_lazy("admin:expenses_expensecategory_changelist"),
                },
            ],
        },
        {
            "title": _("TAG / Pórticos"),
            "items": [
                {
                    "title": _("Resumen TAG"),
                    "icon": "toll",
                    "link": reverse_lazy("admin:tags_tagcharge_analytics"),
                },
                {
                    "title": _("Cobros TAG"),
                    "icon": "receipt_long",
                    "link": reverse_lazy("admin:tags_tagcharge_changelist"),
                },
                {
                    "title": _("Tránsitos"),
                    "icon": "route",
                    "link": reverse_lazy("admin:tags_tagtransit_changelist"),
                },
            ],
        },
        {
            "title": _("Alertas"),
            "items": [
                {
                    "title": _("Centro de alertas"),
                    "icon": "notifications_active",
                    "link": reverse_lazy("admin:alerts_documentalert_changelist"),
                    "badge": str(alert_count) if alert_count else None,
                },
                {
                    "title": _("Mantención"),
                    "icon": "warning",
                    "link": reverse_lazy("admin:alerts_maintenancealert_changelist"),
                },
                {
                    "title": _("Mensajes"),
                    "icon": "mail",
                    "link": reverse_lazy("admin:alerts_notification_overview"),
                },
                {
                    "title": _("Cola mensajes"),
                    "icon": "inbox",
                    "link": reverse_lazy("admin:alerts_notification_changelist"),
                },
            ],
        },
        {
            "title": _("Reportes"),
            "items": [
                {
                    "title": _("Centro reportes"),
                    "icon": "analytics",
                    "link": reverse_lazy("admin:reports_reportexportlog_overview"),
                },
                {
                    "title": _("Exportaciones"),
                    "icon": "download",
                    "link": reverse_lazy("admin:reports_reportexportlog_changelist"),
                },
                {
                    "title": _("Actividad producto"),
                    "icon": "timeline",
                    "link": reverse_lazy("admin:product_analytics_productevent_changelist"),
                },
            ],
        },
        {
            "title": _("Administración / Configuración"),
            "items": [
                {
                    "title": _("Membresías"),
                    "icon": "workspace_premium",
                    "link": reverse_lazy("admin:companies_companylimit_overview"),
                },
                {
                    "title": _("Empresas"),
                    "icon": "apartment",
                    "link": reverse_lazy("admin:companies_company_changelist"),
                },
                {
                    "title": _("Usuarios"),
                    "icon": "group",
                    "link": reverse_lazy("admin:accounts_user_changelist"),
                },
                {
                    "title": _("Sucursales"),
                    "icon": "account_tree",
                    "link": reverse_lazy("admin:companies_branch_changelist"),
                },
                {
                    "title": _("Roles"),
                    "icon": "admin_panel_settings",
                    "link": reverse_lazy("admin:accounts_role_changelist"),
                },
                {
                    "title": _("Auditoría"),
                    "icon": "history",
                    "link": reverse_lazy("admin:audit_auditlog_overview"),
                },
            ],
        },
    ]
