from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User


class RapportsViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_rapports",
            password="secret123",
            role="admin_societe",
            is_staff=True,
        )
        self.client = Client()
        self.client.login(username="admin_rapports", password="secret123")

    def test_rapports_page_renders_for_admin(self):
        url = reverse("webadmin-rapports")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Rapports")
