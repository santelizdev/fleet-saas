"""Vistas administrativas para membresías y límites multiempresa."""

from __future__ import annotations

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from unfold.views import UnfoldModelAdminViewMixin

from apps.accounts.models import User
from apps.documents.models import Attachment
from apps.vehicles.models import Vehicle

from .models import Company, CompanyLimit


class MembershipsOverviewAdminView(UnfoldModelAdminViewMixin, TemplateView):
    """Vista consolidada de planes, límites y consumo actual por empresa."""

    title = _("Membresías")
    permission_required = ()
    template_name = "admin/companies/memberships_overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        companies = Company.objects.all().order_by("name")
        if not self.request.user.is_superuser:
            companies = companies.filter(id=self.request.user.company_id)

        limit_map = {item.company_id: item for item in CompanyLimit.objects.select_related("company").filter(company__in=companies)}
        vehicle_usage = {
            item["company_id"]: item["total"]
            for item in Vehicle.objects.filter(company__in=companies).values("company_id").annotate(total=Count("id"))
        }
        user_usage = {
            item["company_id"]: item["total"]
            for item in User.objects.filter(company__in=companies).values("company_id").annotate(total=Count("id"))
        }
        storage_usage = {
            item["company_id"]: item["total_bytes"]
            for item in Attachment.objects.filter(company__in=companies)
            .values("company_id")
            .annotate(total_bytes=Coalesce(Sum("size_bytes"), 0))
        }

        membership_rows = []
        for company in companies:
            limits = limit_map.get(company.id) or CompanyLimit(company=company)
            bytes_used = int(storage_usage.get(company.id, 0) or 0)
            storage_mb_used = round(bytes_used / (1024 * 1024), 2)
            membership_rows.append(
                {
                    "company": company,
                    "limits": limits,
                    "vehicle_count": vehicle_usage.get(company.id, 0),
                    "user_count": user_usage.get(company.id, 0),
                    "storage_mb_used": storage_mb_used,
                }
            )

        context.update(
            {
                "membership_rows": membership_rows,
                "membership_company_total": len(membership_rows),
            }
        )
        return context
