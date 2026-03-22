from datetime import date

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Capability, Role, RoleCapability, User, UserRole
from apps.alerts.models import AlertState, DocumentAlert, Notification
from apps.companies.models import Company
from apps.documents.models import VehicleDocument
from apps.vehicles.models import Vehicle


class AlertsAPITest(APITestCase):
    def setUp(self):
        self.company_a = Company.objects.create(name="API Alerts A", rut="23.456.789-0")
        self.company_b = Company.objects.create(name="API Alerts B", rut="34.567.890-1")

        self.user_a = User.objects.create_user(
            email="api-alerts-a@local.dev",
            password="Secret123!",
            name="Api Alerts A",
            company=self.company_a,
        )

        vehicle_a = Vehicle.objects.create(company=self.company_a, plate="HH77HH")
        vehicle_b = Vehicle.objects.create(company=self.company_b, plate="II88II")
        doc_a = VehicleDocument.objects.create(
            company=self.company_a,
            vehicle=vehicle_a,
            type=VehicleDocument.TYPE_SEGURO,
            issue_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )
        doc_b = VehicleDocument.objects.create(
            company=self.company_b,
            vehicle=vehicle_b,
            type=VehicleDocument.TYPE_SEGURO,
            issue_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )

        self.alert_a = DocumentAlert.objects.create(
            company=self.company_a,
            vehicle_document=doc_a,
            kind=DocumentAlert.KIND_EXPIRY,
            due_date=doc_a.expiry_date,
            scheduled_for=doc_a.expiry_date,
            message="A",
        )
        self.alert_b = DocumentAlert.objects.create(
            company=self.company_b,
            vehicle_document=doc_b,
            kind=DocumentAlert.KIND_EXPIRY,
            due_date=doc_b.expiry_date,
            scheduled_for=doc_b.expiry_date,
            message="B",
        )

        self.notification_a = Notification.objects.create(
            company=self.company_a,
            document_alert=self.alert_a,
            channel=Notification.CHANNEL_EMAIL,
            recipient="",
            status=Notification.STATUS_FAILED,
            attempts=1,
            last_error="forced",
        )

        doc_read, _ = Capability.objects.get_or_create(code="doc.read")
        doc_manage, _ = Capability.objects.get_or_create(code="doc.manage")
        role = Role.objects.create(company=self.company_a, name="AlertsManager")
        RoleCapability.objects.create(role=role, capability=doc_read)
        RoleCapability.objects.create(role=role, capability=doc_manage)
        UserRole.objects.create(user=self.user_a, role=role)

    def test_document_alert_list_is_company_scoped(self):
        self.client.force_authenticate(self.user_a)
        url = reverse("document-alert-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.data}
        self.assertEqual(ids, {self.alert_a.id})

    def test_acknowledge_and_resolve_actions(self):
        self.client.force_authenticate(self.user_a)
        ack_url = reverse("document-alert-acknowledge", kwargs={"pk": self.alert_a.id})
        ack_response = self.client.post(ack_url)
        self.assertEqual(ack_response.status_code, status.HTTP_200_OK)
        self.assertEqual(ack_response.data["state"], AlertState.ACKNOWLEDGED)

        resolve_url = reverse("document-alert-resolve", kwargs={"pk": self.alert_a.id})
        resolve_response = self.client.post(resolve_url)
        self.assertEqual(resolve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(resolve_response.data["state"], AlertState.RESOLVED)

    def test_notification_requeue_action(self):
        self.client.force_authenticate(self.user_a)
        url = reverse("notification-requeue", kwargs={"pk": self.notification_a.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Notification.STATUS_QUEUED)
        self.assertEqual(response.data["last_error"], "")
