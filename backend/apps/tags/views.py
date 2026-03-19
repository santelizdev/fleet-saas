"""Vistas administrativas para el módulo analítico TAG / pórticos."""

from __future__ import annotations

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.views.generic import TemplateView
from unfold.views import UnfoldModelAdminViewMixin

from .models import TagCharge, TagTransit
from .services import build_tag_snapshot, get_recent_tag_movements, get_top_tag_vehicles


class TagAnalyticsView(UnfoldModelAdminViewMixin, TemplateView):
    """Página analítica principal del módulo TAG dentro del admin."""

    title = "Resumen TAG / Pórticos"
    permission_required = ()
    template_name = "admin/tags/analytics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        company_id = None if request.user.is_superuser else request.user.company_id
        snapshot = build_tag_snapshot(company_id=company_id)
        charges = TagCharge.objects.select_related("road", "gate", "vehicle").order_by("-charge_date", "-id")
        transits = TagTransit.objects.select_related("road", "gate", "vehicle").order_by("-transit_at")
        if company_id:
            charges = charges.filter(company_id=company_id)
            transits = transits.filter(company_id=company_id)

        context.update(
            {
                "tag_snapshot": snapshot,
                "tag_latest_charges": charges[:8],
                "tag_recent_movements": get_recent_tag_movements(company_id=company_id, limit=8),
                "tag_top_vehicles": get_top_tag_vehicles(company_id=company_id, limit=5),
                "tag_by_road": list(
                    charges.values("road__name")
                    .annotate(total_amount=Coalesce(Sum("amount_clp"), 0), total_charges=Count("id"))
                    .order_by("-total_amount", "road__name")[:6]
                ),
                "tag_by_gate": list(
                    transits.values("gate__name", "road__name")
                    .annotate(total_transits=Count("id"))
                    .order_by("-total_transits", "road__name")[:6]
                ),
            }
        )
        return context
