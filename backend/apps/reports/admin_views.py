"""Vistas administrativas del centro de reportes."""

from __future__ import annotations

from django.views.generic import TemplateView
from unfold.views import UnfoldModelAdminViewMixin

from .services import build_report_filters, build_reports_admin_context


class ReportsOverviewAdminView(UnfoldModelAdminViewMixin, TemplateView):
    """Pantalla consolidada de reportes operativos dentro del admin."""

    title = "Centro de reportes"
    permission_required = ()
    template_name = "admin/reports/overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company_id = None if self.request.user.is_superuser else self.request.user.company_id
        filters = build_report_filters(self.request.GET, company_id=company_id)
        context.update(build_reports_admin_context(filters))
        return context
