from datetime import date
from unittest.mock import patch

from django.contrib.auth.signals import user_logged_in
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.alerts.models import DocumentAlert, Notification
from apps.alerts.services import send_notification
from apps.audit.models import AuditLog
from apps.audit.services import audit_request_context
from apps.companies.models import Company
from apps.documents.models import VehicleDocument
from apps.vehicles.models import Vehicle


class AuditSignalsTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.company = Company.objects.create(name="Audit Co", rut="91.111.222-3")
        self.user = User.objects.create_superuser(
            email="audit-admin@local.dev",
            password="Secret123!",
            name="Audit Admin",
            company=self.company,
        )

    def test_login_signal_creates_auth_log(self):
        request = self.factory.post("/admin/login/")
        request.user = self.user
        request.company_id = self.company.id
        request.request_id = "req-login-1"
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        user_logged_in.send(sender=User, request=request, user=self.user)

        log = AuditLog.objects.get(action="auth.login")
        self.assertEqual(log.source, AuditLog.SOURCE_AUTH)
        self.assertEqual(log.status, AuditLog.STATUS_SUCCESS)
        self.assertEqual(log.actor, self.user)
        self.assertEqual(log.request_id, "req-login-1")

    def test_vehicle_create_update_delete_is_audited(self):
        request = self.factory.post("/admin/vehicles/vehicle/add/")
        request.user = self.user
        request.company_id = self.company.id
        request.request_id = "req-veh-1"
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        with audit_request_context(request):
            vehicle = Vehicle.objects.create(company=self.company, plate="AA11AA", current_km=100)
            vehicle.current_km = 250
            vehicle.save()
            vehicle.delete()

        actions = list(AuditLog.objects.filter(object_type="Vehicle").values_list("action", flat=True))
        self.assertIn("vehicles.vehicle.create", actions)
        self.assertIn("vehicles.vehicle.update", actions)
        self.assertIn("vehicles.vehicle.delete", actions)

    @patch("apps.alerts.services.send_mail")
    def test_notification_email_success_is_audited(self, send_mail_mock):
        vehicle = Vehicle.objects.create(company=self.company, plate="BB22BB", current_km=100)
        document = VehicleDocument.objects.create(
            company=self.company,
            vehicle=vehicle,
            type=VehicleDocument.TYPE_SOAP,
            issue_date=date(2026, 1, 1),
            expiry_date=date(2026, 4, 1),
        )
        alert = DocumentAlert.objects.create(
            company=self.company,
            vehicle_document=document,
            kind=DocumentAlert.KIND_EXPIRY,
            due_date=date(2026, 4, 1),
            scheduled_for=date(2026, 3, 25),
            message="Prueba auditoría email",
        )
        notification = Notification.objects.create(
            company=self.company,
            document_alert=alert,
            channel=Notification.CHANNEL_EMAIL,
            recipient="driver@local.dev",
            payload={"message": "hola"},
        )

        send_notification(notification)

        log = AuditLog.objects.get(action="notification.email.sent")
        self.assertEqual(log.source, AuditLog.SOURCE_NOTIFICATION)
        self.assertEqual(log.status, AuditLog.STATUS_SUCCESS)
        self.assertEqual(log.metadata_json["recipient"], "driver@local.dev")
