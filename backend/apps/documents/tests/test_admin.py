from datetime import date

from django.contrib.admin.sites import AdminSite
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.models import Role, User, UserRole
from apps.companies.models import Company
from apps.documents.admin import DriverLicenseAdmin, VehicleDocumentAdmin
from apps.documents.models import DriverLicense, VehicleDocument
from apps.vehicles.models import Vehicle


class VehicleDocumentAdminPilotScopeTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.company = Company.objects.create(name="Docs Company", rut="44.444.444-4")
        self.staff_driver = User.objects.create_user(
            email="pilot@local.dev",
            password="Secret123!",
            name="Pilot",
            company=self.company,
            is_staff=True,
        )
        role = Role.objects.create(company=self.company, name="Piloto")
        UserRole.objects.create(user=self.staff_driver, role=role)

        self.vehicle_owned = Vehicle.objects.create(company=self.company, plate="AA11AA", assigned_driver=self.staff_driver)
        self.vehicle_other = Vehicle.objects.create(company=self.company, plate="BB22BB")
        VehicleDocument.objects.create(
            company=self.company,
            vehicle=self.vehicle_owned,
            type=VehicleDocument.TYPE_SEGURO,
            issue_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )
        VehicleDocument.objects.create(
            company=self.company,
            vehicle=self.vehicle_other,
            type=VehicleDocument.TYPE_SEGURO,
            issue_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )

    def test_pilot_only_sees_assigned_vehicle_documents(self):
        request = self.factory.get("/admin/apps/documents/vehicledocument/")
        request.user = self.staff_driver
        admin_view = VehicleDocumentAdmin(VehicleDocument, self.site)

        docs = list(admin_view.get_queryset(request).values_list("vehicle__plate", flat=True))

        self.assertEqual(docs, ["AA11AA"])

    def test_pilot_only_sees_assigned_vehicle_in_form(self):
        request = self.factory.get("/admin/apps/documents/vehicledocument/add/")
        request.user = self.staff_driver
        admin_view = VehicleDocumentAdmin(VehicleDocument, self.site)
        form = admin_view.get_form(request)()

        vehicles = list(form.fields["vehicle"].queryset.values_list("plate", flat=True))
        self.assertEqual(vehicles, ["AA11AA"])

    def test_document_form_uses_native_date_inputs(self):
        request = self.factory.get("/admin/apps/documents/vehicledocument/add/")
        request.user = self.staff_driver
        admin_view = VehicleDocumentAdmin(VehicleDocument, self.site)
        form = admin_view.get_form(request)()

        self.assertEqual(form.fields["issue_date"].widget.input_type, "date")
        self.assertEqual(form.fields["expiry_date"].widget.input_type, "date")
        self.assertIn("support_image", form.fields)
        self.assertNotIn("previous_version", form.fields)

    def test_driver_license_form_exposes_support_image(self):
        request = self.factory.get("/admin/apps/documents/driverlicense/add/")
        request.user = self.staff_driver
        admin_view = DriverLicenseAdmin(DriverLicense, self.site)
        form = admin_view.get_form(request)()

        self.assertIn("support_image", form.fields)
        self.assertNotIn("previous_version", form.fields)


class DocumentsAdminSuperuserFormTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.client = Client()
        self.site = AdminSite()
        self.company = Company.objects.create(name="Docs Company", rut="44.444.444-4")
        self.other_company = Company.objects.create(name="Other Company", rut="55.555.555-5")
        self.superuser = User.objects.create_superuser(
            email="admin@local.dev",
            password="Secret123!",
            name="Admin",
            company=self.company,
        )
        driver_role = Role.objects.create(company=self.company, name="Piloto")
        self.driver = User.objects.create_user(
            email="driver@local.dev",
            password="Secret123!",
            name="Driver",
            company=self.company,
        )
        UserRole.objects.create(user=self.driver, role=driver_role)
        User.objects.create_user(
            email="other-driver@local.dev",
            password="Secret123!",
            name="Other Driver",
            company=self.other_company,
        )
        self.vehicle = Vehicle.objects.create(company=self.company, plate="AA11AA")
        Vehicle.objects.create(company=self.other_company, plate="BB22BB")
        self.client.force_login(self.superuser)

    def test_blank_driver_license_post_does_not_create_record(self):
        response = self.client.post(reverse("admin:documents_driverlicense_add"), {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DriverLicense.objects.count(), 0)
        self.assertIn("This field is required", response.content.decode())

    def test_blank_vehicle_document_post_does_not_create_record(self):
        response = self.client.post(reverse("admin:documents_vehicledocument_add"), {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(VehicleDocument.objects.count(), 0)
        self.assertIn("This field is required", response.content.decode())

    def test_driver_queryset_waits_for_company_selection(self):
        request = self.factory.get("/admin/documents/driverlicense/add/")
        request.user = self.superuser
        admin_view = DriverLicenseAdmin(DriverLicense, self.site)
        form = admin_view.get_form(request)()

        self.assertEqual(form.fields["driver"].queryset.count(), 0)

        filtered_request = self.factory.get("/admin/documents/driverlicense/add/", {"company": self.company.id})
        filtered_request.user = self.superuser
        filtered_form = admin_view.get_form(filtered_request)()

        drivers = list(filtered_form.fields["driver"].queryset.values_list("email", flat=True))
        self.assertEqual(drivers, ["driver@local.dev"])

    def test_vehicle_queryset_waits_for_company_selection(self):
        request = self.factory.get("/admin/documents/vehicledocument/add/")
        request.user = self.superuser
        admin_view = VehicleDocumentAdmin(VehicleDocument, self.site)
        form = admin_view.get_form(request)()

        self.assertEqual(form.fields["vehicle"].queryset.count(), 0)

        filtered_request = self.factory.get("/admin/documents/vehicledocument/add/", {"company": self.company.id})
        filtered_request.user = self.superuser
        filtered_form = admin_view.get_form(filtered_request)()

        vehicles = list(filtered_form.fields["vehicle"].queryset.values_list("plate", flat=True))
        self.assertEqual(vehicles, ["AA11AA"])

    def test_driver_options_endpoint_is_filtered_by_selected_company(self):
        response = self.client.get(
            reverse("admin:documents_driverlicense_company_options"),
            {"field": "driver", "company_id": self.company.id},
        )

        self.assertEqual(response.status_code, 200)
        labels = [option["label"] for option in response.json()["options"]]
        self.assertEqual(labels, ["Driver"])


class VehicleDocumentChoicesTest(TestCase):
    def test_new_vehicle_document_types_are_available(self):
        self.assertIn((VehicleDocument.TYPE_SEGURO, "SOAP"), VehicleDocument.TYPE_CHOICES)
        self.assertIn((VehicleDocument.TYPE_TECNOMECANICA, "Tecnomecanica"), VehicleDocument.TYPE_CHOICES)
        self.assertIn((VehicleDocument.TYPE_GASES, "Gases"), VehicleDocument.TYPE_CHOICES)
