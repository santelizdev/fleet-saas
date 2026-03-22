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
from apps.audit.services import log_audit_event
from apps.companies.limits import enforce_export_limits, get_effective_limits
from apps.product_analytics.events import track_event
from apps.reports.models import ReportExportLog
from apps.reports.pdf_exports import build_operational_report_pdf
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


def _daily_exports_for(company_id: int, *, report_type: str, today):
    return ReportExportLog.objects.filter(
        company_id=company_id,
        created_at__date=today,
        report_type=report_type,
    ).count()


def _export_limits(company_id: int) -> tuple[int, int]:
    max_rows = int(getattr(settings, "REPORT_MAX_EXPORT_ROWS", 5000))
    max_exports_per_day = int(getattr(settings, "REPORT_MAX_EXPORTS_PER_DAY", 20))
    limits = get_effective_limits(company_id)
    return max_rows, min(max_exports_per_day, limits.max_exports_per_day)


class ExportVehicleCostCSVView(CapabilityAPIView):
    def get(self, request):
        company_id = _company_id_from_request(request)
        today = timezone.localdate()
        filters = build_report_filters(request.GET, company_id=company_id)
        max_rows, max_exports_per_day = _export_limits(company_id)
        exports_today = _daily_exports_for(company_id, report_type="vehicle_costs", today=today)
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
        log_audit_event(
            request=request,
            company_id=company_id,
            actor_id=request.user.id,
            source=AuditLog.SOURCE_API,
            status=AuditLog.STATUS_SUCCESS,
            action="report.export.vehicle_costs",
            object_type="ReportExportLog",
            object_id="vehicle_costs",
            summary="Exportación de costos por vehículo completada",
            after={"format": "csv", "row_count": len(rows)},
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="vehicle_costs.csv"'
        writer = csv.writer(response)
        writer.writerow(["vehicle_id", "plate", "current_km", "total_cost_clp", "cost_per_km"])
        writer.writerows(rows)
        return response


class ExportOperationalSummaryPDFView(CapabilityAPIView):
    def get(self, request):
        company_id = _company_id_from_request(request)
        today = timezone.localdate()
        filters = build_report_filters(request.GET, company_id=company_id)
        max_rows, max_exports_per_day = _export_limits(company_id)
        exports_today = _daily_exports_for(company_id, report_type="operational_summary", today=today)

        try:
            enforce_export_limits(company_id=company_id, actor_id=request.user.id)
        except PermissionDenied as exc:
            return JsonResponse({"detail": str(exc)}, status=429)

        if exports_today >= max_exports_per_day:
            ReportExportLog.objects.create(
                company_id=company_id,
                requested_by=request.user,
                report_type="operational_summary",
                export_format=ReportExportLog.FORMAT_PDF,
                status=ReportExportLog.STATUS_REJECTED,
                note="daily export limit reached",
            )
            return JsonResponse({"detail": "Límite diario de exports alcanzado."}, status=429)

        pdf_bytes, row_count = build_operational_report_pdf(filters)
        if row_count > max_rows:
            ReportExportLog.objects.create(
                company_id=company_id,
                requested_by=request.user,
                report_type="operational_summary",
                export_format=ReportExportLog.FORMAT_PDF,
                status=ReportExportLog.STATUS_REJECTED,
                row_count=row_count,
                note="max rows exceeded",
            )
            return JsonResponse({"detail": "Límite de filas excedido para export."}, status=400)

        ReportExportLog.objects.create(
            company_id=company_id,
            requested_by=request.user,
            report_type="operational_summary",
            export_format=ReportExportLog.FORMAT_PDF,
            status=ReportExportLog.STATUS_COMPLETED,
            row_count=row_count,
        )
        track_event(
            company_id=company_id,
            actor_id=request.user.id,
            event_name="report_exported",
            payload={"report_type": "operational_summary", "format": "pdf", "rows": row_count},
        )
        log_audit_event(
            request=request,
            company_id=company_id,
            actor_id=request.user.id,
            source=AuditLog.SOURCE_API,
            status=AuditLog.STATUS_SUCCESS,
            action="report.export.operational_summary",
            object_type="ReportExportLog",
            object_id="operational_summary",
            summary="Exportación del resumen operacional completada",
            after={"format": "pdf", "row_count": row_count},
        )

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="operational_summary.pdf"'
        return response
