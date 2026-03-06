from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.companies.models import Company
from apps.documents.models import (
    Attachment,
    DriverLicense,
    DriverLicenseAttachment,
    VehicleDocument,
    VehicleDocumentAttachment,
)
from apps.vehicles.models import Vehicle


class DocumentsFlowsTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Docs Co", rut="55.555.555-5")
        self.user = User.objects.create_user(
            email="docs-user@local.dev",
            password="Secret123!",
            name="Docs User",
            company=self.company,
            is_staff=True,
        )
        self.vehicle = Vehicle.objects.create(company=self.company, plate="DD33DD")

    def test_vehicle_document_validates_dates(self):
        with self.assertRaises(ValidationError):
            VehicleDocument.objects.create(
                company=self.company,
                vehicle=self.vehicle,
                type=VehicleDocument.TYPE_SEGURO,
                issue_date=date(2026, 3, 1),
                expiry_date=date(2026, 3, 1),
            )

    def test_vehicle_document_renew_marks_previous_and_creates_new_current(self):
        doc = VehicleDocument.objects.create(
            company=self.company,
            vehicle=self.vehicle,
            type=VehicleDocument.TYPE_SEGURO,
            issue_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
            reminder_days_before=15,
            created_by=self.user,
        )

        renewed = doc.renew(
            issue_date=date(2027, 1, 1),
            expiry_date=date(2027, 12, 31),
            notes="renewed",
            created_by=self.user,
        )

        doc.refresh_from_db()
        self.assertFalse(doc.is_current)
        self.assertEqual(doc.status, VehicleDocument.STATUS_REPLACED)
        self.assertTrue(renewed.is_current)
        self.assertEqual(renewed.previous_version_id, doc.id)
        self.assertEqual(renewed.reminder_days_before, 15)

    def test_driver_license_attachment_requires_same_company(self):
        other_company = Company.objects.create(name="Other Co", rut="66.666.666-6")
        other_user = User.objects.create_user(
            email="other@local.dev",
            password="Secret123!",
            name="Other User",
            company=other_company,
        )
        license_doc = DriverLicense.objects.create(
            company=self.company,
            driver=self.user,
            license_number="L-100",
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
        )
        attachment = Attachment.objects.create(
            company=other_company,
            storage_key="driver-license/other.pdf",
            size_bytes=100,
            mime_type="application/pdf",
        )

        link = DriverLicenseAttachment(
            company=self.company,
            driver_license=license_doc,
            attachment=attachment,
        )
        with self.assertRaises(ValidationError):
            link.save()

        # Sanity: same-company attachments sí deben funcionar
        same_attachment = Attachment.objects.create(
            company=self.company,
            storage_key="driver-license/same.pdf",
            size_bytes=200,
            mime_type="application/pdf",
        )
        ok_link = DriverLicenseAttachment.objects.create(
            company=self.company,
            driver_license=license_doc,
            attachment=same_attachment,
        )
        self.assertIsNotNone(ok_link.id)

    def test_vehicle_document_attachment_flow(self):
        doc = VehicleDocument.objects.create(
            company=self.company,
            vehicle=self.vehicle,
            type=VehicleDocument.TYPE_PERMISO_CIRCULACION,
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
        )
        attachment = Attachment.objects.create(
            company=self.company,
            storage_key="vehicle-docs/permiso.pdf",
            size_bytes=1234,
            mime_type="application/pdf",
        )
        link = VehicleDocumentAttachment.objects.create(
            company=self.company,
            vehicle_document=doc,
            attachment=attachment,
        )
        self.assertIsNotNone(link.id)
