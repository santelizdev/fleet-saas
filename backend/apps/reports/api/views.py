import csv
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Sum
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasCapability
from apps.audit.models import AuditLog
from apps.companies.limits import enforce_export_limits, get_effective_limits
from apps.documents.models import VehicleDocument
from apps.maintenance.models import MaintenanceRecord
from apps.product_analytics.events import track_event
from apps.reports.models import ReportExportLog
from apps.vehicles.models import Vehicle


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
        today = timezone.localdate()
        date_from = parse_date(request.GET.get("date_from") or "") or (today - timedelta(days=30))
        date_to = parse_date(request.GET.get("date_to") or "") or today
        vehicle_id = request.GET.get("vehicle_id")

        maintenance_qs = MaintenanceRecord.objects.filter(
            company_id=company_id,
            service_date__gte=date_from,
            service_date__lte=date_to,
        )
        if vehicle_id:
            maintenance_qs = maintenance_qs.filter(vehicle_id=vehicle_id)

        upcoming_doc_expiries = VehicleDocument.objects.filter(
            company_id=company_id,
            is_current=True,
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=30),
        ).count()
        upcoming_7 = VehicleDocument.objects.filter(
            company_id=company_id,
            is_current=True,
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=7),
        ).count()
        upcoming_15 = VehicleDocument.objects.filter(
            company_id=company_id,
            is_current=True,
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=15),
        ).count()
        upcoming_30 = upcoming_doc_expiries

        maintenance_due = MaintenanceRecord.objects.filter(
            company_id=company_id,
            status=MaintenanceRecord.STATUS_OPEN,
        ).filter(
            next_due_date__lte=today + timedelta(days=30),
        ).count()

        monthly_maintenance_cost = maintenance_qs.aggregate(total=Sum("cost_clp"))["total"] or 0

        top_vehicles = (
            maintenance_qs.values("vehicle_id", "vehicle__plate")
            .annotate(total_cost=Sum("cost_clp"), records=Count("id"))
            .order_by("-total_cost")[:5]
        )

        return Response(
            {
                "date_from": str(date_from),
                "date_to": str(date_to),
                "upcoming_doc_expiries": upcoming_doc_expiries,
                "expiring_7d": upcoming_7,
                "expiring_15d": upcoming_15,
                "expiring_30d": upcoming_30,
                "maintenance_due_30d": maintenance_due,
                "maintenance_cost_clp": monthly_maintenance_cost,
                "top_vehicles": list(top_vehicles),
            }
        )


class VehicleCostReportView(CapabilityAPIView):
    def get(self, request):
        company_id = _company_id_from_request(request)
        vehicle_id = request.GET.get("vehicle_id")
        qs = Vehicle.objects.filter(company_id=company_id).order_by("id")
        if vehicle_id:
            qs = qs.filter(id=vehicle_id)

        rows = []
        for vehicle in qs:
            total_cost = (
                MaintenanceRecord.objects.filter(company_id=company_id, vehicle_id=vehicle.id).aggregate(total=Sum("cost_clp"))[
                    "total"
                ]
                or 0
            )
            km = vehicle.current_km or 0
            cost_per_km = round(total_cost / km, 4) if km > 0 else None
            rows.append(
                {
                    "vehicle_id": vehicle.id,
                    "plate": vehicle.plate,
                    "current_km": km,
                    "total_cost_clp": total_cost,
                    "cost_per_km": cost_per_km,
                }
            )

        return Response({"results": rows})


class ExportVehicleCostCSVView(CapabilityAPIView):
    def get(self, request):
        company_id = _company_id_from_request(request)
        today = timezone.localdate()
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

        rows = []
        for vehicle in Vehicle.objects.filter(company_id=company_id).order_by("id"):
            total_cost = (
                MaintenanceRecord.objects.filter(company_id=company_id, vehicle_id=vehicle.id).aggregate(total=Sum("cost_clp"))[
                    "total"
                ]
                or 0
            )
            km = vehicle.current_km or 0
            cost_per_km = round(total_cost / km, 4) if km > 0 else None
            rows.append([vehicle.id, vehicle.plate, km, total_cost, cost_per_km])

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
