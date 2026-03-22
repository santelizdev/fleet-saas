"""Admin del módulo de reportes y acceso a la vista analítica consolidada."""

from __future__ import annotations

from django.contrib import admin
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from config.admin_scoping import CompanyScopedAdminMixin

from .models import ReportExportLog
from .admin_views import ReportsOverviewAdminView


@admin.register(ReportExportLog)
class ReportExportLogAdmin(CompanyScopedAdminMixin, ModelAdmin):
    list_display = ("id", "company_column", "report_type_column", "export_format_column", "status_column", "row_count_column", "created_at_column")
    list_filter = ("company", "report_type", "export_format", "status")
    search_fields = ("report_type", "note", "requested_by__email")
    form_company_filters = {
        "company": "id",
        "requested_by": "company_id",
    }

    @display(description=_("Empresa"), ordering="company")
    def company_column(self, obj):
        return obj.company

    @display(description=_("Reporte"), ordering="report_type")
    def report_type_column(self, obj):
        return obj.get_report_type_display()

    @display(description=_("Formato"), ordering="export_format")
    def export_format_column(self, obj):
        return obj.get_export_format_display()

    @display(description=_("Estado"), ordering="status")
    def status_column(self, obj):
        return obj.get_status_display()

    @display(description=_("Filas"), ordering="row_count")
    def row_count_column(self, obj):
        return obj.row_count

    @display(description=_("Creado"), ordering="created_at")
    def created_at_column(self, obj):
        return obj.created_at

    def get_urls(self):
        custom_view = self.admin_site.admin_view(ReportsOverviewAdminView.as_view(model_admin=self))
        return [
            path("overview/", custom_view, name="reports_reportexportlog_overview"),
        ] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["reports_overview_url"] = reverse("admin:reports_reportexportlog_overview")
        return super().changelist_view(request, extra_context=extra_context)
