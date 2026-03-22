"""Admin del módulo TAG / pórticos con foco analítico y de conciliación."""

from __future__ import annotations

from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from config.admin_scoping import CompanyScopedAdminMixin

from .models import TagCharge, TagImportBatch, TagTransit, TollGate, TollRoad
from .views import TagAnalyticsView


@admin.register(TollRoad)
class TollRoadAdmin(CompanyScopedAdminMixin, ModelAdmin):
    """Mantiene autopistas disponibles para conciliación TAG."""

    list_display = ("name_column", "company_column", "operator_name_column", "active_badge", "created_at_column")
    list_filter = ("company", "is_active")
    search_fields = ("name", "code", "operator_name")
    form_company_filters = {"company": "id"}

    @display(description=_("Nombre"), ordering="name")
    def name_column(self, obj):
        return obj.name

    @display(description=_("Empresa"), ordering="company")
    def company_column(self, obj):
        return obj.company

    @display(description=_("Operador"), ordering="operator_name")
    def operator_name_column(self, obj):
        return obj.operator_name

    @display(description=_("Creado"), ordering="created_at")
    def created_at_column(self, obj):
        return obj.created_at

    @display(description="Estado", label={True: "success", False: "danger"})
    def active_badge(self, obj):
        return obj.is_active, "Activa" if obj.is_active else "Inactiva"


@admin.register(TollGate)
class TollGateAdmin(CompanyScopedAdminMixin, ModelAdmin):
    """Administra pórticos por autopista y empresa."""

    list_display = ("name_column", "road_column", "company_column", "direction_column", "active_badge")
    list_filter = ("company", "road", "is_active")
    search_fields = ("name", "code", "road__name", "direction")
    list_select_related = ("road", "company")
    form_company_filters = {
        "company": "id",
        "road": "company_id",
    }

    @display(description=_("Nombre"), ordering="name")
    def name_column(self, obj):
        return obj.name

    @display(description=_("Autopista"), ordering="road__name")
    def road_column(self, obj):
        return obj.road

    @display(description=_("Empresa"), ordering="company")
    def company_column(self, obj):
        return obj.company

    @display(description=_("Dirección"), ordering="direction")
    def direction_column(self, obj):
        return obj.direction

    @display(description="Estado", label={True: "success", False: "danger"})
    def active_badge(self, obj):
        return obj.is_active, "Activo" if obj.is_active else "Inactivo"


@admin.register(TagImportBatch)
class TagImportBatchAdmin(CompanyScopedAdminMixin, ModelAdmin):
    """Expone la salud de importaciones o documentos fuente TAG."""

    list_display = ("source_name", "company", "status_badge", "total_rows", "period_start", "period_end", "imported_at")
    list_filter = ("company", "status", "source_name")
    search_fields = ("source_name", "source_file_name", "notes")
    list_select_related = ("company", "created_by")
    readonly_fields = ("imported_at",)
    form_company_filters = {
        "company": "id",
        "created_by": "company_id",
    }

    @display(
        description="Estado",
        label={
            TagImportBatch.STATUS_PENDING: "warning",
            TagImportBatch.STATUS_PROCESSED: "success",
            TagImportBatch.STATUS_FAILED: "danger",
        },
    )
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.company_id = request.user.company_id
        if obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["tag_summary_url"] = reverse("admin:tags_tagcharge_analytics")
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(TagTransit)
class TagTransitAdmin(CompanyScopedAdminMixin, ModelAdmin):
    """Lista operacional de tránsitos con foco en conciliación y trazabilidad."""

    list_display = (
        "transit_at_column",
        "resolved_vehicle",
        "road_column",
        "gate_column",
        "schedule_code_column",
        "day_type_badge",
        "amount_clp_column",
        "match_badge",
    )
    list_filter = ("company", "road", "match_status", "transit_date", "is_weekend")
    search_fields = ("detected_plate", "vehicle__plate", "road__name", "gate__name", "tag_reference", "invoice_reference", "notes")
    list_select_related = ("company", "road", "gate", "vehicle", "batch")
    readonly_fields = ("created_at",)
    date_hierarchy = "transit_date"
    form_company_filters = {
        "company": "id",
        "batch": "company_id",
        "road": "company_id",
        "gate": "company_id",
        "vehicle": "company_id",
    }

    @display(description=_("Fecha de tránsito"), ordering="transit_at")
    def transit_at_column(self, obj):
        return obj.transit_at

    @display(description="Vehículo")
    def resolved_vehicle(self, obj):
        return obj.vehicle.plate if obj.vehicle_id else obj.detected_plate or "Sin patente"

    @display(description=_("Autopista"), ordering="road__name")
    def road_column(self, obj):
        return obj.road

    @display(description=_("Pórtico"), ordering="gate__name")
    def gate_column(self, obj):
        return obj.gate or "-"

    @display(description=_("Código horario"), ordering="schedule_code")
    def schedule_code_column(self, obj):
        return obj.schedule_code or "-"

    @display(description=_("Monto CLP"), ordering="amount_clp")
    def amount_clp_column(self, obj):
        return obj.amount_clp

    @display(description="Tipo día", label={True: "info", False: "success"})
    def day_type_badge(self, obj):
        return obj.is_weekend, "Fin de semana" if obj.is_weekend else "Semana"

    @display(
        description="Conciliación",
        label={
            TagTransit.MATCH_PENDING: "warning",
            TagTransit.MATCH_MATCHED: "success",
            TagTransit.MATCH_UNMATCHED: "danger",
            TagTransit.MATCH_OBSERVED: "info",
        },
    )
    def match_badge(self, obj):
        return obj.match_status, obj.get_match_status_display()

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["tag_summary_url"] = reverse("admin:tags_tagcharge_analytics")
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(TagCharge)
class TagChargeAdmin(CompanyScopedAdminMixin, ModelAdmin):
    """Vista financiera de cobros TAG con acceso al resumen analítico."""

    list_display = (
        "charge_date_column",
        "resolved_vehicle",
        "road_column",
        "gate_column",
        "schedule_code_column",
        "day_type_badge",
        "amount_clp_column",
        "status_badge",
        "related_transit_count",
    )
    list_filter = ("company", "status", "road", "charge_date", "is_weekend")
    search_fields = ("detected_plate", "vehicle__plate", "road__name", "gate__name", "tag_reference", "invoice_reference", "notes")
    list_select_related = ("company", "road", "gate", "vehicle", "transit", "batch")
    readonly_fields = ("created_at",)
    date_hierarchy = "charge_date"
    form_company_filters = {
        "company": "id",
        "transit": "company_id",
        "batch": "company_id",
        "road": "company_id",
        "gate": "company_id",
        "vehicle": "company_id",
    }

    def get_urls(self):
        custom_view = self.admin_site.admin_view(TagAnalyticsView.as_view(model_admin=self))
        return [
            path("analytics/", custom_view, name="tags_tagcharge_analytics"),
        ] + super().get_urls()

    @display(description=_("Fecha del cobro"), ordering="charge_date")
    def charge_date_column(self, obj):
        return obj.charge_date

    @display(description="Vehículo")
    def resolved_vehicle(self, obj):
        return obj.vehicle.plate if obj.vehicle_id else obj.detected_plate or "Sin patente"

    @display(description=_("Autopista"), ordering="road__name")
    def road_column(self, obj):
        return obj.road

    @display(description=_("Pórtico"), ordering="gate__name")
    def gate_column(self, obj):
        return obj.gate or "-"

    @display(description=_("Código horario"), ordering="schedule_code")
    def schedule_code_column(self, obj):
        return obj.schedule_code or "-"

    @display(description=_("Monto CLP"), ordering="amount_clp")
    def amount_clp_column(self, obj):
        return obj.amount_clp

    @display(description="Tipo día", label={True: "info", False: "success"})
    def day_type_badge(self, obj):
        return obj.is_weekend, "Fin de semana" if obj.is_weekend else "Semana"

    @display(
        description="Estado",
        label={
            TagCharge.STATUS_PENDING: "warning",
            TagCharge.STATUS_RECONCILED: "success",
            TagCharge.STATUS_UNMATCHED: "danger",
            TagCharge.STATUS_DISPUTED: "info",
        },
    )
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()

    @display(description="Tránsitos vinculados")
    def related_transit_count(self, obj):
        return 1 if obj.transit_id else 0

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["tag_summary_url"] = reverse("admin:tags_tagcharge_analytics")
        return super().changelist_view(request, extra_context=extra_context)
