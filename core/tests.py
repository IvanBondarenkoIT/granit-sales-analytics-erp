from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class HealthTests(TestCase):
    def test_health_ok_without_login(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "app": "granit-analytics"},
        )


class AuthGateTests(TestCase):
    def test_home_redirects_anonymous_to_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_home_ok_when_logged_in(self):
        user = get_user_model().objects.create_user("analyst", password="test-pass-123")
        self.client.force_login(user)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_login_page_public(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
