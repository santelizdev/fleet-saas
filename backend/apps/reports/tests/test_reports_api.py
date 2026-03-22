from datetime import date, timedelta

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Capability, Role, RoleCapability, User, UserRole
from apps.companies.models import Company
from apps.documents.models import VehicleDocument
from apps.maintenance.models import MaintenanceRecord
from apps.reports.models import ReportExportLog
from apps.vehicles.models import Vehicle


class ReportsAPITest(APITestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(name="Report Co", rut="56.789.012-3")
        self.user = User.objects.create_user(
            email="report@local.dev",
            password="Secret123!",
            name="Reporter",
            company=self.company,
        )
        cap, _ = Capability.objects.get_or_create(code="report.read")
        role = Role.objects.create(company=self.company, name="ReportRole")
        RoleCapability.objects.create(role=role, capability=cap)
        UserRole.objects.create(user=self.user, role=role)

        self.vehicle1 = Vehicle.objects.create(company=self.company, plate="KK11KK", current_km=1000)
        self.vehicle2 = Vehicle.objects.create(company=self.company, plate="LL22LL", current_km=2000)

        MaintenanceRecord.objects.create(
            company=self.company,
            vehicle=self.vehicle1,
            type=MaintenanceRecord.TYPE_PREVENTIVE,
            service_date=date.today() - timedelta(days=5),
            odometer_km=900,
            cost_clp=50000,
            next_due_date=date.today() + timedelta(days=10),
        )
        MaintenanceRecord.objects.create(
            company=self.company,
            vehicle=self.vehicle2,
            type=MaintenanceRecord.TYPE_CORRECTIVE,
            service_date=date.today() - timedelta(days=3),
            odometer_km=1800,
            cost_clp=100000,
            next_due_date=date.today() + timedelta(days=20),
        )
        VehicleDocument.objects.create(
            company=self.company,
            vehicle=self.vehicle1,
            type=VehicleDocument.TYPE_SEGURO,
            issue_date=date.today() - timedelta(days=30),
            expiry_date=date.today() + timedelta(days=15),
        )

        self.client.force_authenticate(self.user)

    def test_dashboard_report_returns_expected_metrics(self):
        url = reverse("report-dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["upcoming_doc_expiries"], 1)
        self.assertEqual(response.data["maintenance_cost_clp"], 150000)
        self.assertEqual(len(response.data["top_vehicles"]), 2)

    def test_vehicle_cost_report_returns_cost_per_km(self):
        url = reverse("report-vehicle-costs")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data["results"]
        self.assertEqual(len(rows), 2)
        vehicle1 = next(r for r in rows if r["vehicle_id"] == self.vehicle1.id)
        self.assertEqual(vehicle1["total_cost_clp"], 50000)
        self.assertEqual(vehicle1["cost_per_km"], 50.0)

    @override_settings(REPORT_MAX_EXPORT_ROWS=10, REPORT_MAX_EXPORTS_PER_DAY=1)
    def test_export_csv_enforces_daily_limit(self):
        url = reverse("report-vehicle-costs-export")
        first = self.client.get(url)
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertIn("vehicle_id,plate,current_km,total_cost_clp,cost_per_km", first.content.decode())
        self.assertEqual(
            ReportExportLog.objects.filter(report_type="vehicle_costs", status=ReportExportLog.STATUS_COMPLETED).count(),
            1,
        )

        second = self.client.get(url)
        self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(
            ReportExportLog.objects.filter(report_type="vehicle_costs", status=ReportExportLog.STATUS_REJECTED).count(),
            1,
        )

    @override_settings(REPORT_MAX_EXPORT_ROWS=200, REPORT_MAX_EXPORTS_PER_DAY=5)
    def test_export_operational_pdf_returns_pdf_and_logs_export(self):
        url = reverse("report-overview-export-pdf")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertEqual(
            ReportExportLog.objects.filter(
                report_type="operational_summary",
                export_format=ReportExportLog.FORMAT_PDF,
                status=ReportExportLog.STATUS_COMPLETED,
            ).count(),
            1,
        )

    @override_settings(RATE_LIMIT_REPORTS_PER_MIN=2)
    def test_reports_rate_limit_by_company(self):
        url = reverse("report-dashboard")
        first = self.client.get(url)
        second = self.client.get(url)
        third = self.client.get(url)
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(third.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
