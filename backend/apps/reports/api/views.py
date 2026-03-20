import csv

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasCapability
from apps.audit.models import AuditLog
from apps.companies.limits import enforce_export_limits, get_effective_limits
from apps.product_analytics.events import track_event
from apps.reports.models import ReportExportLog
from apps.reports.services import build_dashboard_report, build_report_filters, build_vehicle_cost_rows


def _company_id_from_request(request):
    company_id = getattr(request, "company_id", None)
    if company_id is None and getattr(request.user, "is_authenticated", False):
        company_id = getattr(request.user, "company_id", None)
    return company_id


class CapabilityAPIView(APIView):
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = "report.read"


class DashboardReportView(CapabilityAPIView):
    def get(self, request):
        company_id = _company_id_from_request(request)
        filters = build_report_filters(request.GET, company_id=company_id)
        return Response(build_dashboard_report(filters))


class VehicleCostReportView(CapabilityAPIView):
    def get(self, request):
        company_id = _company_id_from_request(request)
        filters = build_report_filters(request.GET, company_id=company_id)
        rows = build_vehicle_cost_rows(filters)
        return Response({"results": rows})


class ExportVehicleCostCSVView(CapabilityAPIView):
    def get(self, request):
        company_id = _company_id_from_request(request)
        today = timezone.localdate()
        filters = build_report_filters(request.GET, company_id=company_id)
        max_rows = int(getattr(settings, "REPORT_MAX_EXPORT_ROWS", 5000))
        max_exports_per_day = int(getattr(settings, "REPORT_MAX_EXPORTS_PER_DAY", 20))
        limits = get_effective_limits(company_id)
        max_exports_per_day = min(max_exports_per_day, limits.max_exports_per_day)

        exports_today = ReportExportLog.objects.filter(
            company_id=company_id,
            created_at__date=today,
            report_type="vehicle_costs",
        ).count()
        try:
            enforce_export_limits(company_id=company_id, actor_id=request.user.id)
        except PermissionDenied as exc:
            return JsonResponse({"detail": str(exc)}, status=429)
        if exports_today >= max_exports_per_day:
            ReportExportLog.objects.create(
                company_id=company_id,
                requested_by=request.user,
                report_type="vehicle_costs",
                export_format=ReportExportLog.FORMAT_CSV,
                status=ReportExportLog.STATUS_REJECTED,
                note="daily export limit reached",
            )
            return JsonResponse({"detail": "Límite diario de exports alcanzado."}, status=429)

        rows = [
            [item["vehicle_id"], item["plate"], item["current_km"], item["total_cost_clp"], item["cost_per_km"]]
            for item in build_vehicle_cost_rows(filters)
        ]

        if len(rows) > max_rows:
            ReportExportLog.objects.create(
                company_id=company_id,
                requested_by=request.user,
                report_type="vehicle_costs",
                export_format=ReportExportLog.FORMAT_CSV,
                status=ReportExportLog.STATUS_REJECTED,
                row_count=len(rows),
                note="max rows exceeded",
            )
            return JsonResponse({"detail": "Límite de filas excedido para export."}, status=400)

        ReportExportLog.objects.create(
            company_id=company_id,
            requested_by=request.user,
            report_type="vehicle_costs",
            export_format=ReportExportLog.FORMAT_CSV,
            status=ReportExportLog.STATUS_COMPLETED,
            row_count=len(rows),
        )
        track_event(
            company_id=company_id,
            actor_id=request.user.id,
            event_name="report_exported",
            payload={"report_type": "vehicle_costs", "rows": len(rows)},
        )
        AuditLog.objects.create(
            company_id=company_id,
            actor_id=request.user.id,
            action="report.export.vehicle_costs",
            object_type="ReportExportLog",
            object_id="vehicle_costs",
            after_json={"format": "csv", "row_count": len(rows)},
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="vehicle_costs.csv"'
        writer = csv.writer(response)
        writer.writerow(["vehicle_id", "plate", "current_km", "total_cost_clp", "cost_per_km"])
        writer.writerows(rows)
        return response
