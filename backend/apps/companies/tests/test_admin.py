from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.companies.models import Company, CompanyLimit
from apps.vehicles.admin import VehicleAdmin
from apps.vehicles.models import Vehicle


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class CompaniesAdminTest(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(name="Alpha Fleet", rut="11.111.111-1")
        self.company_b = Company.objects.create(name="Beta Fleet", rut="22.222.222-2")
        CompanyLimit.objects.create(company=self.company_a, max_vehicles=20, max_users=10)
        CompanyLimit.objects.create(company=self.company_b, max_vehicles=50, max_users=25)
        Vehicle.objects.create(company=self.company_a, plate="AA11AA")
        Vehicle.objects.create(company=self.company_b, plate="BB22BB")

        self.superuser = User.objects.create_superuser(
            email="superadmin@test.local",
            password="Secret123!",
            name="Super Admin",
            company=self.company_a,
        )
        self.factory = RequestFactory()

    def test_memberships_overview_renders(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:companies_companylimit_overview"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Membresías y límites")
        self.assertContains(response, "Alpha Fleet")
        self.assertContains(response, "Beta Fleet")

    def test_company_scope_selector_filters_vehicle_queryset_for_superuser(self):
        request = self.factory.get("/admin/vehicles/vehicle/", {"company_scope": self.company_a.id})
        request.user = self.superuser
        model_admin = VehicleAdmin(Vehicle, AdminSite())
        queryset = model_admin.get_queryset(request)
        self.assertEqual(list(queryset.values_list("plate", flat=True)), ["AA11AA"])

    def test_company_scope_is_accepted_by_vehicle_changelist(self):
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("admin:vehicles_vehicle_changelist"),
            {"company_scope": self.company_a.id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Something’s wrong with your database installation.")
        self.assertContains(response, "AA11AA")
        self.assertNotContains(response, "BB22BB")
