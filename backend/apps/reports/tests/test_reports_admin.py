from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.companies.models import Company
from apps.documents.models import VehicleDocument
from apps.maintenance.models import MaintenanceRecord
from apps.vehicles.models import Vehicle


class ReportsAdminViewTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Admin Reports Co", rut="78.901.234-5")
        self.user = User.objects.create_user(
            email="admin-reports@local.dev",
            password="Secret123!",
            name="Admin Reports",
            company=self.company,
            is_staff=True,
        )
        self.vehicle = Vehicle.objects.create(company=self.company, plate="MM33MM", current_km=1500)
        MaintenanceRecord.objects.create(
            company=self.company,
            vehicle=self.vehicle,
            type=MaintenanceRecord.TYPE_PREVENTIVE,
            service_date=date.today() - timedelta(days=2),
            odometer_km=1300,
            cost_clp=70000,
            next_due_date=date.today() + timedelta(days=12),
            next_due_km=2000,
        )
        VehicleDocument.objects.create(
            company=self.company,
            vehicle=self.vehicle,
            type=VehicleDocument.TYPE_SEGURO,
            issue_date=date.today() - timedelta(days=60),
            expiry_date=date.today() + timedelta(days=20),
        )

    def test_reports_overview_admin_view_renders(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("admin:reports_reportexportlog_overview"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Centro de reportes operativos")
        self.assertContains(response, "Exportar costo por vehículo")
