from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.companies.models import Company
from apps.ops.admin_dashboard import dashboard_callback


class AdminDashboardCallbackTest(TestCase):
    """Cubre el callback del home admin para detectar regresiones de contexto."""

    def setUp(self):
        self.factory = RequestFactory()
        self.company = Company.objects.create(name="Platform", rut="10.100.100-1")
        self.superuser = User.objects.create_superuser(
            email="root@fleet.local",
            password="RootPass123!",
            name="Root",
            company=self.company,
        )

    def test_dashboard_callback_builds_context_without_name_errors(self):
        request = self.factory.get("/admin/")
        request.user = self.superuser

        context = dashboard_callback(request, {})

        self.assertIn("dashboard_kpis", context)
        self.assertIn("dashboard_filters", context)
        self.assertIn("month_label", context["dashboard_filters"])

    def test_admin_index_renders_for_superuser(self):
        self.client.force_login(self.superuser)

        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/static/admin/css/operations_dashboard.css"', html=False)
        self.assertContains(response, "/static/admin/branding/rutacore-logo.svg", html=False)
        self.assertContains(response, "Dashboard analitico")
        self.assertContains(response, "Light")
        self.assertContains(response, "Dark")
