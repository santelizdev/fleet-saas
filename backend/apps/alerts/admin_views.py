"""Vistas administrativas del módulo de mensajes del sistema."""

from __future__ import annotations

from django.views.generic import TemplateView
from django.utils.translation import gettext_lazy as _
from unfold.views import UnfoldModelAdminViewMixin

from .message_center import build_message_center_context, build_message_center_filters


class MessagesOverviewAdminView(UnfoldModelAdminViewMixin, TemplateView):
    """Centro de mensajes internos y emails disparados por el sistema."""

    title = _("Centro de mensajes")
    permission_required = ()
    template_name = "admin/alerts/messages_overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company_id = None if self.request.user.is_superuser else self.request.user.company_id
        filters = build_message_center_filters(self.request.GET, company_id=company_id)
        context.update(build_message_center_context(filters))
        return context
