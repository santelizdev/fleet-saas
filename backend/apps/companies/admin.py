"""Admin de configuración multiempresa alineado con el nuevo backoffice."""

from __future__ import annotations

from django.contrib import admin
from django.urls import path, reverse
from unfold.admin import ModelAdmin
from unfold.decorators import display

from config.admin_scoping import CompanyScopedAdminMixin

from .admin_views import MembershipsOverviewAdminView
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
class CompanyLimitAdmin(CompanyScopedAdminMixin, ModelAdmin):
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
    list_filter = ("company",)
    form_company_filters = {
        "company": "id",
    }

    def get_urls(self):
        custom_view = self.admin_site.admin_view(MembershipsOverviewAdminView.as_view(model_admin=self))
        return [
            path("overview/", custom_view, name="companies_companylimit_overview"),
        ] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["memberships_overview_url"] = reverse("admin:companies_companylimit_overview")
        return super().changelist_view(request, extra_context=extra_context)
