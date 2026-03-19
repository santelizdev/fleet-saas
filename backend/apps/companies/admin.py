"""Admin de configuración multiempresa alineado con el nuevo backoffice."""

from __future__ import annotations

from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.decorators import display

from config.admin_scoping import CompanyScopedAdminMixin

from .models import Branch, Company, CompanyLimit


@admin.register(Company)
class CompanyAdmin(ModelAdmin):
    list_display = ("name", "rut", "plan", "status_badge", "created_at")
    search_fields = ("name", "rut")
    list_filter = ("status", "plan")
    ordering = ("name",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(id=request.user.company_id)

    @display(description="Estado", label={"active": "success", "suspended": "danger"})
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()


@admin.register(Branch)
class BranchAdmin(CompanyScopedAdminMixin, ModelAdmin):
    list_display = ("name", "company", "cost_center_code", "created_at")
    search_fields = ("name", "cost_center_code")
    list_filter = ("company",)
    list_select_related = ("company",)
    form_company_filters = {
        "company": "id",
    }


@admin.register(CompanyLimit)
class CompanyLimitAdmin(ModelAdmin):
    list_display = (
        "company",
        "max_vehicles",
        "max_users",
        "max_storage_mb",
        "max_uploads_per_day",
        "max_exports_per_day",
    )
    search_fields = ("company__name", "company__rut")
    list_select_related = ("company",)
