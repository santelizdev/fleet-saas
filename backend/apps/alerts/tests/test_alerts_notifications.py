from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.alerts.models import AlertState, DocumentAlert, JobRun, Notification
from apps.companies.models import Company
from apps.documents.models import DriverLicense, VehicleDocument
from apps.vehicles.models import Vehicle


class AlertsNotificationsTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Alerts Co", rut="77.777.777-7")
        self.user = User.objects.create_user(
            email="alerts-user@local.dev",
            password="Secret123!",
            name="Alerts User",
            company=self.company,
            is_staff=True,
        )
        self.vehicle = Vehicle.objects.create(
            company=self.company,
            plate="EE44EE",
            assigned_driver=self.user,
        )

    def test_generate_daily_alerts_creates_and_deduplicates(self):
        today = timezone.localdate()

        VehicleDocument.objects.create(
            company=self.company,
            vehicle=self.vehicle,
            type=VehicleDocument.TYPE_SEGURO,
            issue_date=today - timedelta(days=10),
            expiry_date=today + timedelta(days=5),
            reminder_days_before=5,
        )
        DriverLicense.objects.create(
            company=self.company,
            driver=self.user,
            license_number="LIC-200",
            issue_date=today - timedelta(days=20),
            expiry_date=today + timedelta(days=7),
            reminder_days_before=7,
        )

        call_command("generate_daily_alerts")
        self.assertEqual(DocumentAlert.objects.count(), 2)
        self.assertEqual(Notification.objects.filter(status=Notification.STATUS_QUEUED).count(), 2)
        self.assertTrue(JobRun.objects.filter(job_name="generate_daily_alerts").exists())

        # idempotencia: segunda corrida del mismo día no duplica
        call_command("generate_daily_alerts")
        self.assertEqual(DocumentAlert.objects.count(), 2)
        self.assertEqual(Notification.objects.filter(status=Notification.STATUS_QUEUED).count(), 2)

    def test_process_notifications_marks_sent_and_retries_failures(self):
        today = timezone.localdate()
        doc = VehicleDocument.objects.create(
            company=self.company,
            vehicle=self.vehicle,
            type=VehicleDocument.TYPE_SEGURO,
            issue_date=today - timedelta(days=10),
            expiry_date=today + timedelta(days=2),
            reminder_days_before=2,
        )
        alert = DocumentAlert.objects.create(
            company=self.company,
            vehicle_document=doc,
            kind=DocumentAlert.KIND_EXPIRY,
            due_date=doc.expiry_date,
            scheduled_for=today,
            message="Doc vence pronto",
        )
        in_app = Notification.objects.create(
            company=self.company,
            document_alert=alert,
            channel=Notification.CHANNEL_IN_APP,
            recipient=self.user.email,
        )
        email_fail = Notification.objects.create(
            company=self.company,
            document_alert=alert,
            channel=Notification.CHANNEL_EMAIL,
            recipient="",  # fuerza fallo
        )

        call_command("process_notifications", "--limit=10", "--max-attempts=3")

        in_app.refresh_from_db()
        email_fail.refresh_from_db()
        alert.refresh_from_db()

        self.assertEqual(in_app.status, Notification.STATUS_SENT)
        self.assertEqual(alert.state, AlertState.SENT)
        self.assertEqual(email_fail.status, Notification.STATUS_FAILED)
        self.assertEqual(email_fail.attempts, 1)
        self.assertTrue(email_fail.available_at > timezone.now())
        self.assertTrue(JobRun.objects.filter(job_name="process_notifications").exists())
