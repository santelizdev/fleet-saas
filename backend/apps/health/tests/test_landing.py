from django.core import mail
from django.test import TestCase, override_settings


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@test.local",
    SUPPORT_EMAIL="sales@test.local",
)
class HomeLandingTest(TestCase):
    def test_home_landing_renders_quote_form(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Solicitar cotización")
        self.assertContains(response, "RutaCore Fleet SaaS")

    def test_home_landing_post_sends_quote_email(self):
        response = self.client.post(
            "/",
            {
                "full_name": "Saul Santeliz",
                "company_name": "Canserbero Logistics",
                "email": "saul@example.com",
                "phone": "+56912345678",
                "fleet_size": 25,
                "message": "Necesitamos controlar documentos y gastos.",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recibimos tu solicitud")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Canserbero Logistics", mail.outbox[0].subject)
        self.assertIn("Saul Santeliz", mail.outbox[0].body)
