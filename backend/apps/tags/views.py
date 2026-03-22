"""Vistas administrativas para el módulo analítico TAG / pórticos."""

from __future__ import annotations

from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from unfold.views import UnfoldModelAdminViewMixin

from apps.companies.models import Company
from apps.vehicles.models import Vehicle

from .forms import TagCsvImportForm
from .models import TagCharge, TagTransit
from .services import (
    build_tag_snapshot,
    import_manual_tag_csv,
    month_range_from_value,
    normalize_plate,
)


class TagAnalyticsView(UnfoldModelAdminViewMixin, TemplateView):
    """Página analítica principal del módulo TAG dentro del admin."""

    title = "Resumen TAG / Pórticos"
    permission_required = ()
    template_name = "admin/tags/analytics.html"

    def _get_selected_company_id(self):
        request = self.request
        if request.user.is_superuser:
            raw_value = request.POST.get("company") if request.method == "POST" else request.GET.get("company_scope")
            if raw_value:
                try:
                    return int(raw_value)
                except ValueError:
                    return None
            return None
        return request.user.company_id

    def _get_company_scope(self):
        selected_company = self._get_selected_company_id()
        if self.request.user.is_superuser and selected_company:
            try:
                return Company.objects.get(pk=selected_company)
            except Company.DoesNotExist:
                return None
        if self.request.user.is_superuser:
            return None
        return Company.objects.filter(pk=self.request.user.company_id).first()

    def _build_import_form(self):
        request = self.request
        companies = (
            Company.objects.order_by("name")
            if request.user.is_superuser
            else Company.objects.filter(pk=request.user.company_id)
        )
        selected_company_id = self._get_selected_company_id()
        vehicles = Vehicle.objects.none()
        if selected_company_id:
            vehicles = Vehicle.objects.filter(company_id=selected_company_id).order_by("plate")
        elif not request.user.is_superuser:
            vehicles = Vehicle.objects.filter(company_id=request.user.company_id).order_by("plate")
        return TagCsvImportForm(
            request.POST or None,
            request.FILES or None,
            companies=companies,
            vehicles=vehicles,
            show_company=request.user.is_superuser,
            selected_company=selected_company_id,
        )

    def post(self, request, *args, **kwargs):
        form = self._build_import_form()
        if not form.is_valid():
            context = self.get_context_data(import_form=form)
            return self.render_to_response(context)

        company = form.cleaned_data.get("company") if request.user.is_superuser else request.user.company
        if company is None:
            messages.error(request, "Debes seleccionar una empresa para importar TAG.")
            return redirect("admin:tags_tagcharge_analytics")

        try:
            result = import_manual_tag_csv(
                company=company,
                vehicle=form.cleaned_data["vehicle"],
                uploaded_file=form.cleaned_data["csv_file"],
                source_name=form.cleaned_data["source_name"],
                created_by=request.user,
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
            messages.error(request, str(exc))
            context = self.get_context_data(import_form=form)
            return self.render_to_response(context)
        if result.error_count:
            messages.warning(
                request,
                f"TAG importado con observaciones. Cobros: {result.created_charges}, "
                f"duplicados: {result.duplicate_count}, errores: {result.error_count}.",
            )
        else:
            messages.success(
                request,
                f"TAG importado correctamente. Cobros: {result.created_charges}, "
                f"conciliados: {result.matched_items}, duplicados: {result.duplicate_count}.",
            )
        month_value = (result.batch.period_start or "").strftime("%Y-%m") if result.batch.period_start else ""
        redirect_url = "admin:tags_tagcharge_analytics"
        if month_value:
            return redirect(f"{reverse_lazy(redirect_url)}?month={month_value}")
        return redirect(redirect_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        scoped_company = self._get_company_scope()
        company_id = scoped_company.id if scoped_company else None
        month_start, month_end, month_value = month_range_from_value(request.GET.get("month"))
        plate_query = (request.GET.get("plate") or "").strip()
        normalized_plate = normalize_plate(plate_query)

        snapshot = build_tag_snapshot(company_id=company_id)
        charges = TagCharge.objects.select_related("road", "gate", "vehicle", "batch").order_by("-billed_at", "-charge_date", "-id")
        transits = TagTransit.objects.select_related("road", "gate", "vehicle", "batch").order_by("-transit_at")
        if company_id:
            charges = charges.filter(company_id=company_id)
            transits = transits.filter(company_id=company_id)

        charges = charges.filter(charge_date__range=(month_start, month_end))
        transits = transits.filter(transit_date__range=(month_start, month_end))
        if normalized_plate:
            plate_filter = Q(vehicle__plate__icontains=plate_query) | Q(detected_plate__icontains=normalized_plate)
            charges = charges.filter(plate_filter)
            transits = transits.filter(plate_filter)

        filtered_total = charges.aggregate(total=Coalesce(Sum("amount_clp"), 0))["total"]
        weekday_total = charges.filter(is_weekend=False).aggregate(total=Coalesce(Sum("amount_clp"), 0))["total"]
        weekend_total = charges.filter(is_weekend=True).aggregate(total=Coalesce(Sum("amount_clp"), 0))["total"]
        filtered_count = charges.count()
        unmatched_count = charges.filter(status=TagCharge.STATUS_UNMATCHED).count()
        duplicate_count = (
            charges.values("vehicle_id", "detected_plate", "billed_at", "gate_id", "amount_clp", "tag_reference", "invoice_reference")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .count()
        )
        latest_batches = (
            charges.exclude(batch__isnull=True)
            .values("batch_id", "batch__source_name", "batch__source_file_name", "batch__imported_at")
            .annotate(total_amount=Coalesce(Sum("amount_clp"), 0), total_items=Count("id"))
            .order_by("-batch__imported_at")[:5]
        )

        context.update(
            {
                "tag_snapshot": snapshot,
                "tag_filter_month": month_value,
                "tag_filter_plate": plate_query,
                "tag_filtered_total": filtered_total,
                "tag_weekday_total": weekday_total,
                "tag_weekend_total": weekend_total,
                "tag_filtered_count": filtered_count,
                "tag_filtered_unmatched_count": unmatched_count,
                "tag_filtered_duplicate_count": duplicate_count,
                "tag_import_form": kwargs.get("import_form") or self._build_import_form(),
                "tag_company_scope": company_id,
                "tag_latest_batches": list(latest_batches),
                "tag_latest_charges": charges[:8],
                "tag_recent_movements": list(transits[:8]),
                "tag_top_vehicles": list(
                    charges.filter(vehicle__isnull=False)
                    .values("vehicle_id", "vehicle__plate")
                    .annotate(total_amount=Coalesce(Sum("amount_clp"), 0), total_charges=Count("id"))
                    .order_by("-total_amount", "vehicle__plate")[:5]
                ),
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
                "tag_detail_rows": charges[:200],
            }
        )
        return context
