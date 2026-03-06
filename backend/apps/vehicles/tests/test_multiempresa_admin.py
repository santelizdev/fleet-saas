from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.companies.models import Company
from apps.vehicles.admin import VehicleAdmin
from apps.vehicles.models import Vehicle


class MultiempresaAdminIsolationTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
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

        Vehicle.objects.create(company=self.company_a, plate="AA11AA")
        Vehicle.objects.create(company=self.company_b, plate="BB22BB")

    def test_staff_only_sees_own_company_vehicles_in_admin_queryset(self):
        request = self.factory.get("/admin/apps/vehicles/vehicle/")
        request.user = self.staff_a

        admin_view = VehicleAdmin(Vehicle, self.site)
        company_ids = list(admin_view.get_queryset(request).values_list("company_id", flat=True))

        self.assertEqual(company_ids, [self.company_a.id])
