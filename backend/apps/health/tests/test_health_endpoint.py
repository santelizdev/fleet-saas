from django.test import Client, TestCase


class HealthEndpointTest(TestCase):
    def test_health_endpoint_returns_expected_shape(self):
        client = Client()
        response = client.get("/health/")

        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertIn("status", payload)
        self.assertIn("db", payload)
        self.assertIn("redis", payload)
        self.assertIn(payload["status"], ["ok", "degraded"])
