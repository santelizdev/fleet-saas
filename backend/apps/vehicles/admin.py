"""Admin de vehículos con foco operacional y acceso a vista 360."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.admin.exceptions import NotRegistered
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper
from django.urls import path, reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import display

from apps.accounts.models import Driver
from config.admin_scoping import CompanyScopedAdminMixin

from .admin_views import VehicleOverviewAdminView
from .models import Vehicle


class _ProxyRemoteField:
    """Envuelve remote_field para que el widget relacionado apunte al admin proxy."""

    def __init__(self, remote_field, model):
        self._remote_field = remote_field
        self.model = model
        self.limit_choices_to = remote_field.limit_choices_to
        self.on_delete = getattr(remote_field, "on_delete", None)

    def get_related_field(self):
        return self._remote_field.get_related_field()


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

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name != "assigned_driver" or formfield is None or db_field.name in self.raw_id_fields:
            return formfield

        try:
            driver_admin = self.admin_site.get_model_admin(Driver)
        except NotRegistered:
            return formfield

        inner_widget = formfield.widget.widget if isinstance(formfield.widget, RelatedFieldWidgetWrapper) else formfield.widget
        formfield.widget = RelatedFieldWidgetWrapper(
            inner_widget,
            _ProxyRemoteField(db_field.remote_field, Driver),
            self.admin_site,
            can_add_related=driver_admin.has_add_permission(request),
            can_change_related=driver_admin.has_change_permission(request),
            can_delete_related=driver_admin.has_delete_permission(request),
            can_view_related=driver_admin.has_view_permission(request),
        )
        return formfield

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
