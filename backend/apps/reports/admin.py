from django.contrib import admin

from config.admin_scoping import CompanyScopedAdminMixin

from .models import ReportExportLog


@admin.register(ReportExportLog)
class ReportExportLogAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "report_type", "export_format", "status", "row_count", "created_at")
    list_filter = ("company", "report_type", "export_format", "status")
    search_fields = ("report_type", "note", "requested_by__email")
    form_company_filters = {
        "company": "id",
        "requested_by": "company_id",
    }
