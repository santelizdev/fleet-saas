from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.alerts.models import DocumentAlert, Notification
from apps.companies.models import Company
from apps.documents.models import VehicleDocument
from apps.vehicles.models import Vehicle


class MessagesAdminViewTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Messages Co", rut="45.678.901-2")
        self.user = User.objects.create_user(
            email="messages-admin@local.dev",
            password="Secret123!",
            name="Messages Admin",
            company=self.company,
            is_staff=True,
        )
        vehicle = Vehicle.objects.create(company=self.company, plate="MS11MS", assigned_driver=self.user)
        document = VehicleDocument.objects.create(
            company=self.company,
            vehicle=vehicle,
            type=VehicleDocument.TYPE_SEGURO,
            issue_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )
        alert = DocumentAlert.objects.create(
            company=self.company,
            vehicle_document=document,
            kind=DocumentAlert.KIND_EXPIRY,
            due_date=document.expiry_date,
            scheduled_for=document.expiry_date,
            message="Seguro por vencer",
        )
        Notification.objects.create(
            company=self.company,
            document_alert=alert,
            channel=Notification.CHANNEL_IN_APP,
            recipient=self.user.email,
            payload={"message": "Seguro por vencer"},
        )
        Notification.objects.create(
            company=self.company,
            document_alert=alert,
            channel=Notification.CHANNEL_EMAIL,
            recipient=self.user.email,
            payload={"message": "Seguro por vencer"},
            status=Notification.STATUS_SENT,
        )

    def test_messages_overview_admin_view_renders(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("admin:alerts_notification_overview"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Centro de mensajes internos")
        self.assertContains(response, "Emails recientes")
