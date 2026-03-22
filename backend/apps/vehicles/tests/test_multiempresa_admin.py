from django.test import Client
from django.urls import reverse

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from django.core.exceptions import ValidationError

from apps.accounts.models import Role, User, UserRole
from apps.companies.models import Company
from apps.vehicles.admin import VehicleAdmin
from apps.vehicles.models import Vehicle


class MultiempresaAdminIsolationTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.client = Client()
        self.site = AdminSite()

        self.company_a = Company.objects.create(name="Company A", rut="11.111.111-1")
        self.company_b = Company.objects.create(name="Company B", rut="22.222.222-2")

        self.staff_a = User.objects.create_user(
            email="staff-a@local.dev",
            password="Secret123!",
            name="Staff A",
            company=self.company_a,
            is_staff=True,
        )
        self.staff_b = User.objects.create_user(
            email="staff-b@local.dev",
            password="Secret123!",
            name="Staff B",
            company=self.company_b,
            is_staff=True,
        )
        self.superuser = User.objects.create_superuser(
            email="admin@local.dev",
            password="Secret123!",
            name="Admin",
            company=self.company_a,
        )

        Vehicle.objects.create(company=self.company_a, plate="AA11AA")
        Vehicle.objects.create(company=self.company_b, plate="BB22BB")

    def test_staff_only_sees_own_company_vehicles_in_admin_queryset(self):
        request = self.factory.get("/admin/apps/vehicles/vehicle/")
        request.user = self.staff_a

        admin_view = VehicleAdmin(Vehicle, self.site)
        company_ids = list(admin_view.get_queryset(request).values_list("company_id", flat=True))

        self.assertEqual(company_ids, [self.company_a.id])

    def test_assigned_driver_options_are_filtered_by_selected_company(self):
        role = Role.objects.create(company=self.company_a, name="Driver")
        UserRole.objects.create(user=self.staff_a, role=role)
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("admin:vehicles_vehicle_company_options"),
            {"field": "assigned_driver", "company_id": self.company_a.id},
        )

        self.assertEqual(response.status_code, 200)
        options = response.json()["options"]
        labels = [option["label"] for option in options]
        self.assertEqual(labels, ["Staff A"])

    def test_vehicle_rejects_assigned_user_without_driver_role(self):
        office_user = User.objects.create_user(
            email="office-a@local.dev",
            password="Secret123!",
            name="Office A",
            company=self.company_a,
            is_staff=True,
        )
        vehicle = Vehicle(company=self.company_a, plate="CC33CC", assigned_driver=office_user)
        with self.assertRaisesMessage(ValidationError, "rol de conductor"):
            vehicle.full_clean()

    def test_vehicle_form_uses_spanish_labels(self):
        self.client.force_login(self.superuser)
        vehicle = Vehicle.objects.create(company=self.company_a, plate="CC33CC")

        response = self.client.get(reverse("admin:vehicles_vehicle_change", args=[vehicle.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Empresa")
        self.assertContains(response, "Sucursal")
        self.assertContains(response, "Marca")
        self.assertContains(response, "Modelo")
        self.assertContains(response, "Año")
        self.assertContains(response, "Número de motor")
        self.assertContains(response, "Kilometraje actual")
        self.assertContains(response, "Conductor asignado")
        self.assertNotContains(response, ">Company<")
        self.assertNotContains(response, ">Brand<")
