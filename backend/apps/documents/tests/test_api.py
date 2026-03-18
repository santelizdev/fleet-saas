import shutil
import tempfile
from datetime import date
from io import BytesIO

from django.conf import settings
from django.core.files.storage import default_storage
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.functional import empty
from rest_framework import status
from rest_framework.test import APITestCase
from PIL import Image

from apps.accounts.models import Capability, Role, RoleCapability, User, UserRole
from apps.companies.models import Company, CompanyLimit
from apps.documents.models import Attachment, VehicleDocument
from apps.product_analytics.models import ProductEvent
from apps.vehicles.models import Vehicle


def make_test_upload(name="test.png", image_format="PNG", size=(2400, 1600), color=(0, 128, 255)):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format=image_format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{image_format.lower()}")


class DocumentsAPITest(APITestCase):
    def setUp(self):
        self.previous_media_root = settings.MEDIA_ROOT
        self.media_root = tempfile.mkdtemp(prefix="fleet-docs-tests-")
        settings.MEDIA_ROOT = self.media_root
        default_storage._wrapped = empty
        self.company_a = Company.objects.create(name="API Docs A", rut="88.888.888-8")
        self.company_b = Company.objects.create(name="API Docs B", rut="12.345.678-9")

        self.user_a = User.objects.create_user(
            email="api-docs-a@local.dev",
            password="Secret123!",
            name="Api Docs A",
            company=self.company_a,
        )
        self.user_read_only = User.objects.create_user(
            email="api-docs-ro@local.dev",
            password="Secret123!",
            name="Api Docs ReadOnly",
            company=self.company_a,
        )

        self.vehicle_a = Vehicle.objects.create(company=self.company_a, plate="FF55FF")
        self.vehicle_b = Vehicle.objects.create(company=self.company_b, plate="GG66GG")

        doc_read, _ = Capability.objects.get_or_create(code="doc.read")
        doc_manage, _ = Capability.objects.get_or_create(code="doc.manage")

        role_manage = Role.objects.create(company=self.company_a, name="DocManager")
        RoleCapability.objects.create(role=role_manage, capability=doc_read)
        RoleCapability.objects.create(role=role_manage, capability=doc_manage)
        UserRole.objects.create(user=self.user_a, role=role_manage)

        role_ro = Role.objects.create(company=self.company_a, name="DocReader")
        RoleCapability.objects.create(role=role_ro, capability=doc_read)
        UserRole.objects.create(user=self.user_read_only, role=role_ro)

    def tearDown(self):
        settings.MEDIA_ROOT = self.previous_media_root
        default_storage._wrapped = empty
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

    def test_vehicle_document_crud_and_company_scope(self):
        self.client.force_authenticate(self.user_a)
        create_url = reverse("vehicle-document-list")
        payload = {
            "company": self.company_b.id,  # debe ignorarse y forzar company del request
            "vehicle": self.vehicle_a.id,
            "type": VehicleDocument.TYPE_SEGURO,
            "issue_date": "2026-01-01",
            "expiry_date": "2026-12-31",
            "reminder_days_before": 10,
            "notes": "first version",
            "support_image": make_test_upload(),
        }
        response = self.client.post(create_url, payload, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_id = response.data["id"]
        self.assertEqual(response.data["support_attachment"]["mime_type"], "image/jpeg")
        self.assertIn("/media/", response.data["support_attachment"]["file_url"])

        VehicleDocument.objects.create(
            company=self.company_b,
            vehicle=self.vehicle_b,
            type=VehicleDocument.TYPE_SEGURO,
            issue_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )

        list_response = self.client.get(create_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        returned_ids = {item["id"] for item in list_response.data}
        self.assertEqual(returned_ids, {created_id})

        patch_url = reverse("vehicle-document-detail", kwargs={"pk": created_id})
        patch_response = self.client.patch(patch_url, {"notes": "patched"}, format="json")
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data["notes"], "patched")

    def test_vehicle_document_renew_endpoint(self):
        self.client.force_authenticate(self.user_a)
        doc = VehicleDocument.objects.create(
            company=self.company_a,
            vehicle=self.vehicle_a,
            type=VehicleDocument.TYPE_PERMISO_CIRCULACION,
            issue_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
            reminder_days_before=30,
        )
        renew_url = reverse("vehicle-document-renew", kwargs={"pk": doc.id})
        response = self.client.post(
            renew_url,
            {
                "issue_date": "2027-01-01",
                "expiry_date": "2027-12-31",
                "notes": "renewed by api",
                "support_image": make_test_upload(name="renew.webp", image_format="WEBP"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        doc.refresh_from_db()
        self.assertFalse(doc.is_current)
        self.assertEqual(doc.status, VehicleDocument.STATUS_REPLACED)
        self.assertTrue(response.data["is_current"])
        self.assertEqual(response.data["support_attachment"]["mime_type"], "image/jpeg")
        self.assertNotIn("previous_version", response.data)
        self.assertTrue(
            ProductEvent.objects.filter(company=self.company_a, event_name="document_renewed").exists()
        )

    def test_doc_manage_permission_required_for_write(self):
        self.client.force_authenticate(self.user_read_only)
        create_url = reverse("vehicle-document-list")
        payload = {
            "vehicle": self.vehicle_a.id,
            "type": VehicleDocument.TYPE_SEGURO,
            "issue_date": "2026-01-01",
            "expiry_date": "2026-12-31",
        }
        response = self.client.post(create_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_pack_endpoint_creates_template_documents(self):
        self.client.force_authenticate(self.user_a)
        url = reverse("vehicle-document-create-pack")
        response = self.client.post(
            url,
            {"vehicle_id": self.vehicle_a.id, "issue_date": "2026-01-01", "expiry_date": "2026-12-31"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["created_document_ids"]), 4)
        created_types = set(VehicleDocument.objects.filter(id__in=response.data["created_document_ids"]).values_list("type", flat=True))
        self.assertEqual(
            created_types,
            {
                VehicleDocument.TYPE_PERMISO_CIRCULACION,
                VehicleDocument.TYPE_TECNOMECANICA,
                VehicleDocument.TYPE_SEGURO,
                VehicleDocument.TYPE_GASES,
            },
        )

    def test_integrated_support_image_upload_limit_enforced(self):
        self.client.force_authenticate(self.user_a)
        CompanyLimit.objects.create(company=self.company_a, max_uploads_per_day=0)
        url = reverse("vehicle-document-list")
        payload = {
            "vehicle": self.vehicle_a.id,
            "type": VehicleDocument.TYPE_SEGURO,
            "issue_date": "2026-01-01",
            "expiry_date": "2026-12-31",
            "support_image": make_test_upload(),
        }
        response = self.client.post(url, payload, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Attachment.objects.count(), 0)
