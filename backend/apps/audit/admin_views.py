"""Vista operativa del módulo de auditoría."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from unfold.views import UnfoldModelAdminViewMixin

from apps.companies.models import Company

from .models import AuditLog


class AuditOverviewAdminView(UnfoldModelAdminViewMixin, TemplateView):
    title = _("Centro de auditoría")
    permission_required = ()
    template_name = "admin/audit/overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = AuditLog.objects.select_related("company", "actor").order_by("-created_at")
        companies = Company.objects.order_by("name") if self.request.user.is_superuser else Company.objects.filter(id=self.request.user.company_id)

        selected_company = self.request.GET.get("company")
        selected_source = self.request.GET.get("source") or ""
        selected_status = self.request.GET.get("status") or ""
        q = (self.request.GET.get("q") or "").strip()
        days = int(self.request.GET.get("days") or 14)
        since = timezone.now() - timedelta(days=days)

        queryset = queryset.filter(created_at__gte=since)
        if not self.request.user.is_superuser:
            queryset = queryset.filter(company_id=self.request.user.company_id)
        elif selected_company:
            queryset = queryset.filter(company_id=selected_company)
        if selected_source:
            queryset = queryset.filter(source=selected_source)
        if selected_status:
            queryset = queryset.filter(status=selected_status)
        if q:
            queryset = queryset.filter(
                Q(action__icontains=q)
                | Q(summary__icontains=q)
                | Q(object_id__icontains=q)
                | Q(request_id__icontains=q)
            )

        recent_logs = list(queryset[:80])
        summary_base = queryset
        by_source = {
            item["source"]: item["total"]
            for item in summary_base.values("source").annotate(total=Count("id"))
        }

        context.update(
            {
                "audit_logs": recent_logs,
                "audit_kpis": {
                    "total": summary_base.count(),
                    "failed": summary_base.filter(status=AuditLog.STATUS_FAILED).count(),
                    "auth": by_source.get(AuditLog.SOURCE_AUTH, 0),
                    "notifications": by_source.get(AuditLog.SOURCE_NOTIFICATION, 0),
                    "admin": by_source.get(AuditLog.SOURCE_ADMIN, 0),
                    "api": by_source.get(AuditLog.SOURCE_API, 0),
                },
                "audit_companies": companies,
                "audit_sources": AuditLog.SOURCE_CHOICES,
                "audit_statuses": AuditLog.STATUS_CHOICES,
                "audit_filters": {
                    "company": selected_company or "",
                    "source": selected_source,
                    "status": selected_status,
                    "q": q,
                    "days": days,
                },
                "audit_day_options": (7, 14, 30, 90),
            }
        )
        return context
