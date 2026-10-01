from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
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
        self.assertContains(response, reverse("register"))

    def test_register_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newbie",
                "password1": "UniquePass-48291",
                "password2": "UniquePass-48291",
            },
        )
        self.assertRedirects(response, reverse("home"))
        user = get_user_model().objects.get(username="newbie")
        self.assertFalse(user.is_staff)
        # Follow-up request is authenticated
        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)

    @override_settings(ALLOW_REGISTRATION=False)
    def test_register_closed_returns_403(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 403)

    @override_settings(ALLOW_REGISTRATION=False)
    def test_login_hides_register_link_when_closed(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("register"))


class QtyFilterTests(TestCase):
    def test_russian_format(self):
        from decimal import Decimal

        from django.utils import translation

        from core.templatetags.numbers import qty

        with translation.override("ru"):
            self.assertEqual(qty(Decimal("0.250")), "0,25")
            self.assertEqual(qty(Decimal("65.000")), "65")
            self.assertEqual(qty(Decimal("0.125")), "0,125")
            self.assertEqual(qty(Decimal("1234.500")).replace("\xa0", " "), "1 234,5")
            self.assertEqual(qty(Decimal("0")), "0")

    def test_english_format(self):
        from decimal import Decimal

        from django.utils import translation

        from core.templatetags.numbers import qty

        with translation.override("en"):
            self.assertEqual(qty(Decimal("0.250")), "0.25")
            self.assertEqual(qty(Decimal("1234.500")), "1,234.5")
            self.assertEqual(qty(None), "")
