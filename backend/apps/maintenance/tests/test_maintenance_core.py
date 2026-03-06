from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.alerts.models import MaintenanceAlert, Notification
from apps.companies.models import Company
from apps.maintenance.models import MaintenanceRecord, VehicleOdometerLog
from apps.vehicles.models import Vehicle


class MaintenanceCoreTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Maint Co", rut="45.678.901-2")
        self.user = User.objects.create_user(
            email="maint@local.dev",
            password="Secret123!",
            name="Maint",
            company=self.company,
        )
        self.vehicle = Vehicle.objects.create(company=self.company, plate="JJ99JJ", current_km=1000, assigned_driver=self.user)

    def test_odometer_log_updates_vehicle_current_km_only_when_greater(self):
        VehicleOdometerLog.objects.create(
            company=self.company,
            vehicle=self.vehicle,
            km=900,
            source=VehicleOdometerLog.SOURCE_MANUAL,
            recorded_by=self.user,
        )
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.current_km, 1000)

        VehicleOdometerLog.objects.create(
            company=self.company,
            vehicle=self.vehicle,
            km=1500,
            source=VehicleOdometerLog.SOURCE_MANUAL,
            recorded_by=self.user,
        )
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.current_km, 1500)

    def test_generate_daily_alerts_creates_maintenance_date_and_km_alerts(self):
        today = timezone.localdate()
        MaintenanceRecord.objects.create(
            company=self.company,
            vehicle=self.vehicle,
            type=MaintenanceRecord.TYPE_PREVENTIVE,
            service_date=today - timedelta(days=30),
            odometer_km=1000,
            cost_clp=10000,
            next_due_date=today,
            next_due_km=1500,
        )
        self.vehicle.current_km = 1600
        self.vehicle.save(update_fields=["current_km"])

        call_command("generate_daily_alerts")

        self.assertEqual(MaintenanceAlert.objects.count(), 2)
        self.assertEqual(Notification.objects.filter(maintenance_alert__isnull=False).count(), 2)
