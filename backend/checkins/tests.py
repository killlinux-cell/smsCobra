import base64
from datetime import date, datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from shifts.models import ShiftAssignment
from sites.models import Site
from checkins.late_utils import is_start_late
from checkins.models import Checkin

User = get_user_model()


def _selfie_upload():
    # PNG 1x1 pixel (valide pour Pillow / ImageField)
    raw = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    return SimpleUploadedFile("selfie.png", raw, content_type="image/png")


def _profile_upload():
    raw = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    return SimpleUploadedFile("profile.png", raw, content_type="image/png")


class CheckinFlowTests(TestCase):
    def setUp(self):
        self._face_patcher = patch(
            "checkins.face_verify.verify_selfie_against_profile",
            return_value=(True, 0.91, ""),
        )
        self._face_patcher.start()
        self.addCleanup(self._face_patcher.stop)

        self.user = User.objects.create_user(username="guard1", password="pass12345", role="vigile")
        self.site = Site.objects.create(
            name="Site A",
            address="Abidjan",
            expected_start_time=time(8, 0),
            expected_end_time=time(17, 0),
            latitude=5.348,
            longitude=-4.024,
        )
        now_local = timezone.localtime()
        start_dt = now_local - timedelta(hours=1)
        end_dt = now_local + timedelta(hours=8)
        self.assignment = ShiftAssignment.objects.create(
            guard=self.user,
            site=self.site,
            shift_date=start_dt.date(),
            start_time=start_dt.time().replace(second=0, microsecond=0),
            end_time=end_dt.time().replace(second=0, microsecond=0),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.user.profile_photo = _profile_upload()
        self.user.save(update_fields=["profile_photo"])

    def _issue_verification_token(self, checkin_type: str) -> str:
        challenge = self.client.post(
            "/api/v1/checkins/biometric/challenge",
            {
                "assignment_id": self.assignment.id,
                "checkin_type": checkin_type,
                "device_id": "test_device",
            },
            format="json",
        )
        self.assertEqual(challenge.status_code, 201)
        challenge_id = challenge.data["challenge_id"]
        verify = self.client.post(
            "/api/v1/checkins/biometric/verify",
            {"challenge_id": challenge_id, "selfie": _selfie_upload()},
            format="multipart",
        )
        self.assertEqual(verify.status_code, 200)
        return verify.data["verification_token"]

    def test_start_checkin_requires_selfie(self):
        response = self.client.post(
            "/api/v1/checkins/start",
            {
                "assignment": str(self.assignment.id),
                "latitude": "5.348",
                "longitude": "-4.024",
                "photo": _selfie_upload(),
                "verification_token": self._issue_verification_token("start"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)

    def test_presence_requires_start(self):
        r = self.client.post(
            "/api/v1/checkins/presence",
            {
                "assignment": str(self.assignment.id),
                "latitude": "5.348",
                "longitude": "-4.024",
                "photo": _selfie_upload(),
                "verification_token": self._issue_verification_token("presence"),
            },
            format="multipart",
        )
        self.assertEqual(r.status_code, 400)

    def test_presence_allowed_after_start(self):
        self.client.post(
            "/api/v1/checkins/start",
            {
                "assignment": str(self.assignment.id),
                "latitude": "5.348",
                "longitude": "-4.024",
                "photo": _selfie_upload(),
                "verification_token": self._issue_verification_token("start"),
            },
            format="multipart",
        )
        r = self.client.post(
            "/api/v1/checkins/presence",
            {
                "assignment": str(self.assignment.id),
                "latitude": "5.348",
                "longitude": "-4.024",
                "photo": _selfie_upload(),
                "verification_token": self._issue_verification_token("presence"),
            },
            format="multipart",
        )
        self.assertEqual(r.status_code, 201)

    def test_presence_rate_limit(self):
        self.client.post(
            "/api/v1/checkins/start",
            {
                "assignment": str(self.assignment.id),
                "latitude": "5.348",
                "longitude": "-4.024",
                "photo": _selfie_upload(),
                "verification_token": self._issue_verification_token("start"),
            },
            format="multipart",
        )
        r1 = self.client.post(
            "/api/v1/checkins/presence",
            {
                "assignment": str(self.assignment.id),
                "latitude": "5.348",
                "longitude": "-4.024",
                "photo": _selfie_upload(),
                "verification_token": self._issue_verification_token("presence"),
            },
            format="multipart",
        )
        self.assertEqual(r1.status_code, 201)
        r2 = self.client.post(
            "/api/v1/checkins/presence",
            {
                "assignment": str(self.assignment.id),
                "latitude": "5.348",
                "longitude": "-4.024",
                "photo": _selfie_upload(),
                "verification_token": self._issue_verification_token("presence"),
            },
            format="multipart",
        )
        self.assertEqual(r2.status_code, 201)

    def test_geofence_gps_margin_reduces_false_outside(self):
        """~120 m au nord du site : hors rayon 100 m mais dans rayon + marge GPS."""
        self.site.geofence_radius_meters = 100
        self.site.geofence_gps_margin_meters = 50
        self.site.save()
        r = self.client.post(
            "/api/v1/checkins/start",
            {
                "assignment": str(self.assignment.id),
                "latitude": "5.349078",
                "longitude": "-4.024",
                "photo": _selfie_upload(),
                "verification_token": self._issue_verification_token("start"),
            },
            format="multipart",
        )
        self.assertEqual(r.status_code, 201)
        c = Checkin.objects.latest("id")
        self.assertTrue(c.within_geofence)
        self.assertIsNotNone(c.distance_from_site_meters)
        self.assertGreater(c.distance_from_site_meters, 100)

    def test_geofence_strict_when_margin_zero(self):
        self.site.geofence_radius_meters = 100
        self.site.geofence_gps_margin_meters = 0
        self.site.save()
        r = self.client.post(
            "/api/v1/checkins/start",
            {
                "assignment": str(self.assignment.id),
                "latitude": "5.349078",
                "longitude": "-4.024",
                "photo": _selfie_upload(),
                "verification_token": self._issue_verification_token("start"),
            },
            format="multipart",
        )
        self.assertEqual(r.status_code, 201)
        c = Checkin.objects.latest("id")
        self.assertFalse(c.within_geofence)

    @override_settings(BIOMETRIC_ENFORCEMENT_MODE="observe")
    def test_observation_mode_allows_checkin_without_token(self):
        r = self.client.post(
            "/api/v1/checkins/start",
            {
                "assignment": str(self.assignment.id),
                "latitude": "5.348",
                "longitude": "-4.024",
                "photo": _selfie_upload(),
            },
            format="multipart",
        )
        self.assertEqual(r.status_code, 201)

    def test_start_rejected_when_before_assignment_window(self):
        now_local = timezone.localtime()
        start_dt = now_local + timedelta(hours=2)
        end_dt = now_local + timedelta(hours=10)
        self.assignment.shift_date = start_dt.date()
        self.assignment.start_time = start_dt.time().replace(second=0, microsecond=0)
        self.assignment.end_time = end_dt.time().replace(second=0, microsecond=0)
        self.assignment.save(update_fields=["shift_date", "start_time", "end_time"])

        r = self.client.post(
            "/api/v1/checkins/start",
            {
                "assignment": str(self.assignment.id),
                "latitude": "5.348",
                "longitude": "-4.024",
                "photo": _selfie_upload(),
                "verification_token": self._issue_verification_token("start"),
            },
            format="multipart",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("hors créneau", r.data.get("detail", ""))


class IsStartLateTests(TestCase):
    """was_late doit utiliser late_tolerance_minutes + fuseau du site."""

    def setUp(self):
        self.user = User.objects.create_user(username="late_guard", password="p", role="vigile")
        self.site = Site.objects.create(
            name="PETROCI",
            address="Abidjan",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=5.0,
            longitude=-4.0,
            late_tolerance_minutes=45,
            timezone="Africa/Abidjan",
        )
        self.assignment = ShiftAssignment.objects.create(
            guard=self.user,
            site=self.site,
            shift_date=date(2026, 4, 6),
            start_time=time(6, 0),
            end_time=time(18, 0),
        )

    def test_seconds_after_start_not_late_with_45min_tolerance(self):
        tz = ZoneInfo("Africa/Abidjan")
        ts = datetime(2026, 4, 6, 6, 0, 30, tzinfo=tz)
        self.assertFalse(is_start_late(ts, self.assignment))

    def test_exactly_at_tolerance_deadline_not_late(self):
        tz = ZoneInfo("Africa/Abidjan")
        ts = datetime(2026, 4, 6, 6, 45, 0, tzinfo=tz)
        self.assertFalse(is_start_late(ts, self.assignment))

    def test_after_tolerance_deadline_is_late(self):
        tz = ZoneInfo("Africa/Abidjan")
        ts = datetime(2026, 4, 6, 6, 45, 1, tzinfo=tz)
        self.assertTrue(is_start_late(ts, self.assignment))


class HandoverCheckinTests(TestCase):
    def setUp(self):
        self._face_patcher = patch(
            "checkins.face_verify.verify_selfie_against_profile",
            return_value=(True, 0.91, ""),
        )
        self._face_patcher.start()
        self.addCleanup(self._face_patcher.stop)

        self.guard_a = User.objects.create_user(username="guard_a", password="x", role="vigile")
        self.guard_b = User.objects.create_user(username="guard_b", password="x", role="vigile")
        self.site = Site.objects.create(
            name="Site B",
            address="Abidjan",
            expected_start_time=time(6, 0),
            expected_end_time=time(19, 0),
            latitude=5.348,
            longitude=-4.024,
        )
        self.incoming = ShiftAssignment.objects.create(
            guard=self.guard_b,
            site=self.site,
            shift_date=date.today(),
            start_time=time(6, 30),
            end_time=time(18, 30),
        )
        self.outgoing = ShiftAssignment.objects.create(
            guard=self.guard_a,
            site=self.site,
            shift_date=date.today(),
            start_time=time(18, 0),
            end_time=time(6, 30),
            relieved_by=self.incoming,
        )
        self.client_a = APIClient()
        self.client_a.force_authenticate(self.guard_a)
        self.client_b = APIClient()
        self.client_b.force_authenticate(self.guard_b)
        self.guard_a.profile_photo = _profile_upload()
        self.guard_b.profile_photo = _profile_upload()
        self.guard_a.save(update_fields=["profile_photo"])
        self.guard_b.save(update_fields=["profile_photo"])

    def _issue_verification_token(self, client: APIClient, assignment_id: int, checkin_type: str) -> str:
        challenge = client.post(
            "/api/v1/checkins/biometric/challenge",
            {
                "assignment_id": assignment_id,
                "checkin_type": checkin_type,
                "device_id": "handover_device",
            },
            format="json",
        )
        self.assertEqual(challenge.status_code, 201)
        challenge_id = challenge.data["challenge_id"]
        verify = client.post(
            "/api/v1/checkins/biometric/verify",
            {"challenge_id": challenge_id, "selfie": _selfie_upload()},
            format="multipart",
        )
        self.assertEqual(verify.status_code, 200)
        return verify.data["verification_token"]

    def test_end_blocked_until_relief_start(self):
        r = self.client_a.post(
            "/api/v1/checkins/end",
            {
                "assignment": str(self.outgoing.id),
                "latitude": "5.348",
                "longitude": "-4.024",
                "photo": _selfie_upload(),
                "verification_token": self._issue_verification_token(self.client_a, self.outgoing.id, "end"),
            },
            format="multipart",
        )
        self.assertEqual(r.status_code, 400)

    def test_end_allowed_after_relief_start(self):
        fake_now = datetime.combine(
            self.incoming.shift_date,
            time(6, 35),
            tzinfo=ZoneInfo("Africa/Abidjan"),
        )
        with patch("checkins.views.timezone.now", return_value=fake_now):
            self.client_b.post(
                "/api/v1/checkins/start",
                {
                    "assignment": str(self.incoming.id),
                    "latitude": "5.348",
                    "longitude": "-4.024",
                    "photo": _selfie_upload(),
                    "verification_token": self._issue_verification_token(self.client_b, self.incoming.id, "start"),
                },
                format="multipart",
            )
        r = self.client_a.post(
            "/api/v1/checkins/end",
            {
                "assignment": str(self.outgoing.id),
                "latitude": "5.348",
                "longitude": "-4.024",
                "photo": _selfie_upload(),
                "verification_token": self._issue_verification_token(self.client_a, self.outgoing.id, "end"),
            },
            format="multipart",
        )
        self.assertEqual(r.status_code, 201)


class FaceBiometricVerifyRejectTests(TestCase):
    """Refus explicite quand la comparaison selfie / photo d’enrôlement échoue."""

    def setUp(self):
        self.user = User.objects.create_user(username="face_guard", password="p", role="vigile")
        self.site = Site.objects.create(
            name="Site Face",
            address="Abidjan",
            expected_start_time=time(8, 0),
            expected_end_time=time(17, 0),
            latitude=5.348,
            longitude=-4.024,
        )
        self.assignment = ShiftAssignment.objects.create(
            guard=self.user,
            site=self.site,
            shift_date=date.today(),
            start_time=time(8, 0),
            end_time=time(17, 0),
        )
        self.user.profile_photo = _profile_upload()
        self.user.save(update_fields=["profile_photo"])
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_verify_returns_403_on_face_mismatch(self):
        with patch(
            "checkins.face_verify.verify_selfie_against_profile",
            return_value=(False, 0.35, "face_mismatch"),
        ):
            ch = self.client.post(
                "/api/v1/checkins/biometric/challenge",
                {
                    "assignment_id": self.assignment.id,
                    "checkin_type": "start",
                    "device_id": "t",
                },
                format="json",
            )
            self.assertEqual(ch.status_code, 201)
            v = self.client.post(
                "/api/v1/checkins/biometric/verify",
                {"challenge_id": ch.data["challenge_id"], "selfie": _selfie_upload()},
                format="multipart",
            )
        self.assertEqual(v.status_code, 403)
        self.assertEqual(v.data.get("reason"), "face_mismatch")
