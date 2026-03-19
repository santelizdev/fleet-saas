"""Admin de vehículos con foco operacional y acceso a vista 360."""

from __future__ import annotations

from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import display

from config.admin_scoping import CompanyScopedAdminMixin

from .admin_views import VehicleOverviewAdminView
from .models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(CompanyScopedAdminMixin, ModelAdmin):
    """Expone métricas y accesos rápidos para la operación diaria de flota."""

    list_display = (
        "plate_header",
        "status_badge",
        "company",
        "branch",
        "assigned_driver",
        "current_km",
        "documents_link",
        "overview_link",
    )
    search_fields = ("plate", "brand", "model", "vin", "engine_number", "assigned_driver__name")
    list_filter = ("company", "status", "branch")
    list_select_related = ("company", "branch", "assigned_driver")
    ordering = ("plate",)
    fieldsets = (
        ("Identificación", {"fields": ("company", "branch", "plate", "status")}),
        ("Ficha del vehículo", {"fields": (("brand", "model", "year"), ("vin", "engine_number"), "current_km")}),
        ("Responsable", {"fields": ("assigned_driver",)}),
    )
    form_company_filters = {
        "company": "id",
        "branch": "company_id",
        "assigned_driver": "company_id",
    }

    def get_urls(self):
        custom_view = self.admin_site.admin_view(VehicleOverviewAdminView.as_view(model_admin=self))
        return [
            path("<path:object_id>/overview/", custom_view, name="vehicles_vehicle_overview"),
        ] + super().get_urls()

    @display(header=True, ordering="plate", description="Vehículo")
    def plate_header(self, obj):
        subtitle = " ".join(part for part in [obj.brand, obj.model] if part).strip() or "Sin ficha técnica"
        return [obj.plate, subtitle, obj.plate[:2].upper()]

    @display(
        description="Estado",
        ordering="status",
        label={
            Vehicle.STATUS_ACTIVE: "success",
            Vehicle.STATUS_INACTIVE: "danger",
        },
    )
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()

    @display(description="Documentos")
    def documents_link(self, obj):
        count = obj.documents.filter(is_current=True).count()
        url = f"{reverse('admin:documents_vehicledocument_changelist')}?vehicle__id__exact={obj.id}"
        return format_html('<a href="{}">{} vigentes</a>', url, count)

    @display(description="Vista 360")
    def overview_link(self, obj):
        url = reverse("admin:vehicles_vehicle_overview", args=[obj.pk])
        return format_html('<a class="button" href="{}">Abrir</a>', url)
