from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Capability, Role, RoleCapability, User, UserRole
from apps.companies.models import Company, CompanyLimit
from apps.product_analytics.models import ProductEvent


class VehicleAPITest(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Vehicle Co", rut="61.111.222-3")
        self.user = User.objects.create_user(
            email="vehicle-api@local.dev",
            password="Secret123!",
            name="Vehicle API",
            company=self.company,
        )
        cap_read, _ = Capability.objects.get_or_create(code="vehicle.read")
        cap_manage, _ = Capability.objects.get_or_create(code="vehicle.manage")
        role = Role.objects.create(company=self.company, name="VehicleManager")
        RoleCapability.objects.create(role=role, capability=cap_read)
        RoleCapability.objects.create(role=role, capability=cap_manage)
        UserRole.objects.create(user=self.user, role=role)
        self.client.force_authenticate(self.user)

    def test_vehicle_create_and_csv_import(self):
        create_url = reverse("vehicle-list")
        create_resp = self.client.post(create_url, {"plate": "VA-1001", "brand": "A"}, format="json")
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)

        csv_url = reverse("vehicle-import-csv")
        csv_text = "plate,brand,model,current_km\nVA-1002,Toyota,Yaris,1000\nVA-1003,Kia,Rio,1500\n"
        csv_resp = self.client.post(csv_url, {"csv_content": csv_text}, format="json")
        self.assertEqual(csv_resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(csv_resp.data["created"], 2)

        self.assertTrue(ProductEvent.objects.filter(company=self.company, event_name="vehicle_created").exists())

    def test_vehicle_limit_blocks_csv_import(self):
        CompanyLimit.objects.create(company=self.company, max_vehicles=1)
        create_url = reverse("vehicle-list")
        self.client.post(create_url, {"plate": "VL-0001"}, format="json")

        csv_url = reverse("vehicle-import-csv")
        csv_text = "plate\nVL-0002\n"
        resp = self.client.post(csv_url, {"csv_content": csv_text}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
