from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.alerts.models import DocumentAlert, JobRun, Notification
from apps.companies.models import Company
from apps.documents.models import Attachment
from apps.vehicles.models import Vehicle
from apps.documents.models import VehicleDocument
from datetime import timedelta

from django.utils import timezone


class SuperadminOpsTest(APITestCase):
    def setUp(self):
        self.super_company = Company.objects.create(name="Platform", rut="10.000.000-0")
        self.superuser = User.objects.create_superuser(
            email="root@fleet.local",
            password="RootPass123!",
            name="Root",
            company=self.super_company,
        )
        self.client.force_authenticate(self.superuser)

    def test_quick_onboarding_creates_company_users_vehicles(self):
        url = reverse("superadmin-quickstart")
        payload = {
            "company_name": "Pilot Co",
            "rut": "20.000.000-0",
            "branch_name": "Casa Matriz",
            "manager_email": "manager@pilot.local",
            "driver_email": "driver@pilot.local",
            "vehicles": ["PT-1001", "PT-1002"],
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["vehicle_ids"]), 2)

    def test_superadmin_overview_returns_ops_data(self):
        company = Company.objects.create(name="Pilot 2", rut="30.000.000-0")
        vehicle = Vehicle.objects.create(company=company, plate="OV-1001")
        doc = VehicleDocument.objects.create(
            company=company,
            vehicle=vehicle,
            type=VehicleDocument.TYPE_SEGURO,
            issue_date=timezone.localdate() - timedelta(days=1),
            expiry_date=timezone.localdate(),
            reminder_days_before=0,
        )
        alert = DocumentAlert.objects.create(
            company=company,
            vehicle_document=doc,
            kind=DocumentAlert.KIND_EXPIRY,
            due_date=doc.expiry_date,
            scheduled_for=doc.expiry_date,
            message="x",
        )
        Notification.objects.create(
            company=company,
            channel=Notification.CHANNEL_IN_APP,
            status=Notification.STATUS_FAILED,
            recipient="",
            document_alert=alert,
        )
        JobRun.objects.create(
            job_name="generate_daily_alerts",
            status=JobRun.STATUS_SUCCESS,
            details={"created_alerts": 1},
            started_at=self.superuser.created_at,
            finished_at=self.superuser.created_at,
        )
        Attachment.objects.create(
            company=company,
            storage_key="ops/test.bin",
            original_name="test.bin",
            size_bytes=4096,
            mime_type="application/octet-stream",
        )
        url = reverse("superadmin-overview")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("companies", response.data)
        self.assertIn("job_runs_24h", response.data)
        self.assertIn("failed_notifications_total", response.data)
