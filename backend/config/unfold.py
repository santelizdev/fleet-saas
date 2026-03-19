"""Configuración compartida del admin Unfold y helpers de navegación."""

from __future__ import annotations

from typing import Any

from django.urls import reverse_lazy
from django.utils import timezone

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
            "title": "Resumen",
            "separator": True,
            "items": [
                {
                    "title": "Dashboard",
                    "icon": "dashboard",
                    "link": reverse_lazy("admin:index"),
                },
            ],
        },
        {
            "title": "Flota",
            "items": [
                {
                    "title": "Vehículos",
                    "icon": "directions_car",
                    "link": reverse_lazy("admin:vehicles_vehicle_changelist"),
                },
                {
                    "title": "Odómetro",
                    "icon": "speed",
                    "link": reverse_lazy("admin:maintenance_vehicleodometerlog_changelist"),
                },
                {
                    "title": "Conductores",
                    "icon": "badge",
                    "link": reverse_lazy("admin:accounts_user_changelist"),
                },
            ],
        },
        {
            "title": "Documentos",
            "items": [
                {
                    "title": "Documentos vehículo",
                    "icon": "description",
                    "link": reverse_lazy("admin:documents_vehicledocument_changelist"),
                },
                {
                    "title": "Licencias",
                    "icon": "article",
                    "link": reverse_lazy("admin:documents_driverlicense_changelist"),
                },
            ],
        },
        {
            "title": "Mantenimientos",
            "items": [
                {
                    "title": "Plan mantenimiento",
                    "icon": "build",
                    "link": reverse_lazy("admin:maintenance_maintenancerecord_changelist"),
                },
            ],
        },
        {
            "title": "Gastos",
            "items": [
                {
                    "title": "Gastos de flota",
                    "icon": "payments",
                    "link": reverse_lazy("admin:expenses_vehicleexpense_changelist"),
                },
                {
                    "title": "Categorías",
                    "icon": "category",
                    "link": reverse_lazy("admin:expenses_expensecategory_changelist"),
                },
            ],
        },
        {
            "title": "TAG / Pórticos",
            "items": [
                {
                    "title": "Resumen TAG",
                    "icon": "toll",
                    "link": reverse_lazy("admin:tags_tagcharge_analytics"),
                },
                {
                    "title": "Cobros TAG",
                    "icon": "receipt_long",
                    "link": reverse_lazy("admin:tags_tagcharge_changelist"),
                },
                {
                    "title": "Tránsitos",
                    "icon": "route",
                    "link": reverse_lazy("admin:tags_tagtransit_changelist"),
                },
            ],
        },
        {
            "title": "Alertas",
            "items": [
                {
                    "title": "Centro de alertas",
                    "icon": "notifications_active",
                    "link": reverse_lazy("admin:alerts_documentalert_changelist"),
                    "badge": str(alert_count) if alert_count else None,
                },
                {
                    "title": "Mantención",
                    "icon": "warning",
                    "link": reverse_lazy("admin:alerts_maintenancealert_changelist"),
                },
                {
                    "title": "Notificaciones",
                    "icon": "mail",
                    "link": reverse_lazy("admin:alerts_notification_changelist"),
                },
            ],
        },
        {
            "title": "Reportes",
            "items": [
                {
                    "title": "Exportaciones",
                    "icon": "analytics",
                    "link": reverse_lazy("admin:reports_reportexportlog_changelist"),
                },
                {
                    "title": "Actividad producto",
                    "icon": "timeline",
                    "link": reverse_lazy("admin:product_analytics_productevent_changelist"),
                },
            ],
        },
        {
            "title": "Administración / Configuración",
            "items": [
                {
                    "title": "Empresas",
                    "icon": "apartment",
                    "link": reverse_lazy("admin:companies_company_changelist"),
                },
                {
                    "title": "Sucursales",
                    "icon": "account_tree",
                    "link": reverse_lazy("admin:companies_branch_changelist"),
                },
                {
                    "title": "Roles",
                    "icon": "admin_panel_settings",
                    "link": reverse_lazy("admin:accounts_role_changelist"),
                },
                {
                    "title": "Auditoría",
                    "icon": "history",
                    "link": reverse_lazy("admin:audit_auditlog_changelist"),
                },
            ],
        },
    ]
