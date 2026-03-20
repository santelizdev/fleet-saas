"""Admin del módulo de reportes y acceso a la vista analítica consolidada."""

from __future__ import annotations

from django.contrib import admin
from django.urls import path, reverse
from unfold.admin import ModelAdmin

from config.admin_scoping import CompanyScopedAdminMixin

from .models import ReportExportLog
from .admin_views import ReportsOverviewAdminView


@admin.register(ReportExportLog)
class ReportExportLogAdmin(CompanyScopedAdminMixin, ModelAdmin):
    list_display = ("id", "company", "report_type", "export_format", "status", "row_count", "created_at")
    list_filter = ("company", "report_type", "export_format", "status")
    search_fields = ("report_type", "note", "requested_by__email")
    form_company_filters = {
        "company": "id",
        "requested_by": "company_id",
    }

    def get_urls(self):
        custom_view = self.admin_site.admin_view(ReportsOverviewAdminView.as_view(model_admin=self))
        return [
            path("overview/", custom_view, name="reports_reportexportlog_overview"),
        ] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["reports_overview_url"] = reverse("admin:reports_reportexportlog_overview")
        return super().changelist_view(request, extra_context=extra_context)
