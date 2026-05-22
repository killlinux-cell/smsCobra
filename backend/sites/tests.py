from django.test import TestCase

from .models import Site
from .serializers import SiteSerializer


class SiteOptionalCoordinatesTests(TestCase):
    def test_create_site_without_coordinates(self):
        data = {
            "name": "Entrepôt Nord",
            "address": "Zone industrielle",
            "site_manager_phone": "+22507000000",
            "timezone": "Africa/Abidjan",
            "expected_start_time": "06:00:00",
            "expected_end_time": "18:00:00",
        }
        ser = SiteSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)
        site = ser.save()
        self.assertIsNone(site.latitude)
        self.assertIsNone(site.longitude)

    def test_reject_latitude_without_longitude(self):
        data = {
            "name": "Site incomplet",
            "address": "Rue test",
            "site_manager_phone": "+22507000001",
            "latitude": "5.348",
        }
        ser = SiteSerializer(data=data)
        self.assertFalse(ser.is_valid())
