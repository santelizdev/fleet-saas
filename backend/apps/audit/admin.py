from django.contrib import admin
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from config.admin_scoping import CompanyScopedAdminMixin

from .admin_views import AuditOverviewAdminView
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(CompanyScopedAdminMixin, ModelAdmin):
    list_display = (
        "created_at_column",
        "source_badge",
        "status_badge",
        "company_column",
        "actor_column",
        "action_column",
        "summary_column",
        "object_ref",
    )
    list_filter = ("company", "source", "status", "action", "object_type")
    search_fields = ("action", "summary", "object_type", "object_id", "actor__email", "request_id", "remote_addr")
    readonly_fields = (
        "company",
        "actor",
        "source",
        "status",
        "action",
        "summary",
        "object_type",
        "object_id",
        "request_id",
        "remote_addr",
        "metadata_json",
        "before_json",
        "after_json",
        "created_at",
    )
    fields = readonly_fields
    ordering = ("-created_at",)

    def get_urls(self):
        custom_view = self.admin_site.admin_view(AuditOverviewAdminView.as_view(model_admin=self))
        return [path("overview/", custom_view, name="audit_auditlog_overview")] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["audit_overview_url"] = reverse("admin:audit_auditlog_overview")
        return super().changelist_view(request, extra_context=extra_context)

    @display(description=_("Fecha"), ordering="created_at")
    def created_at_column(self, obj):
        return obj.created_at

    @display(description=_("Fuente"), label={"admin": "info", "api": "success", "auth": "warning", "system": "info", "notification": "primary"})
    def source_badge(self, obj):
        return obj.source, obj.get_source_display()

    @display(description=_("Resultado"), label={"success": "success", "failed": "danger", "info": "info", "warning": "warning"})
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()

    @display(description=_("Empresa"), ordering="company")
    def company_column(self, obj):
        return obj.company

    @display(description=_("Actor"), ordering="actor__email")
    def actor_column(self, obj):
        return obj.actor or "Sistema"

    @display(description=_("Acción"), ordering="action")
    def action_column(self, obj):
        return obj.action

    @display(description=_("Resumen"), ordering="summary")
    def summary_column(self, obj):
        return obj.summary or "-"

    @display(description=_("Objeto"))
    def object_ref(self, obj):
        return f"{obj.object_type}:{obj.object_id}"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
