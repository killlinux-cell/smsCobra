from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import ControllerSiteAssignment, ControllerVisit
from alerts.models import LateAlert
from reports.activity_feed import build_activity_events
from shifts.models import FixedPost, ShiftAssignment
from sites.models import Site

User = get_user_model()


class ActivityFeedTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(
            name="Site Feed",
            address="Abidjan",
            expected_start_time="08:00",
            expected_end_time="17:00",
            latitude=5.348,
            longitude=-4.024,
        )
        self.vigile = User.objects.create_user(
            username="v_feed",
            password="x",
            role=User.Role.VIGILE,
        )
        self.controller = User.objects.create_user(
            username="c_feed",
            password="x",
            role=User.Role.CONTROLEUR,
            first_name="Ctrl",
            last_name="Test",
        )
        ControllerSiteAssignment.objects.create(controller=self.controller, site=self.site)

    def test_includes_controleur_created(self):
        kinds = {e["kind"] for e in build_activity_events(limit=200)}
        self.assertIn("controleur_created", kinds)

    def test_includes_controller_visit(self):
        ControllerVisit.objects.create(controller=self.controller, site=self.site)
        kinds = {e["kind"] for e in build_activity_events(limit=200)}
        self.assertIn("controller_visit", kinds)

    def test_includes_guard_replaced(self):
        replacement = User.objects.create_user(username="rep_feed", password="x", role=User.Role.VIGILE)
        a = ShiftAssignment.objects.create(
            guard=replacement,
            original_guard=self.vigile,
            site=self.site,
            shift_date=timezone.localdate(),
            start_time="06:00",
            end_time="18:00",
            status=ShiftAssignment.Status.REPLACED,
        )
        ShiftAssignment.objects.filter(pk=a.pk).update(updated_at=timezone.now())
        kinds = {e["kind"] for e in build_activity_events(limit=200)}
        self.assertIn("guard_replaced", kinds)

    def test_site_filter_includes_controller_visit(self):
        ControllerVisit.objects.create(controller=self.controller, site=self.site)
        events = build_activity_events(limit=50, site_id=self.site.id)
        self.assertTrue(any(e["kind"] == "controller_visit" for e in events))

    def test_site_filter_includes_controleur_when_assigned(self):
        events = build_activity_events(limit=50, site_id=self.site.id)
        self.assertTrue(any(e["kind"] == "controleur_created" for e in events))

    def test_includes_alert_acknowledged(self):
        admin = User.objects.create_user(
            username="admin_ack",
            password="x",
            role=User.Role.ADMIN_SOCIETE,
            first_name="Marie",
            last_name="Admin",
        )
        assignment = ShiftAssignment.objects.create(
            guard=self.vigile,
            site=self.site,
            shift_date=timezone.localdate(),
            start_time="06:00",
            end_time="18:00",
        )
        ack_time = timezone.now()
        LateAlert.objects.create(
            assignment=assignment,
            message="Retard prise de service : v_feed sur Site Feed",
            status=LateAlert.Status.ACKNOWLEDGED,
            admin_recipient=admin,
            acknowledged_at=ack_time,
        )
        matches = [
            e
            for e in build_activity_events(limit=200)
            if e["kind"] == "alert_acknowledged"
        ]
        self.assertEqual(len(matches), 1)
        self.assertIn("Marie", matches[0]["body"])
        self.assertIn("acquitté", matches[0]["body"].lower())

    def test_fixed_post_replacement_on_update(self):
        titular = User.objects.create_user(username="tit_feed", password="x", role=User.Role.VIGILE)
        repl = User.objects.create_user(username="repl_feed", password="x", role=User.Role.VIGILE)
        fp = FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=titular,
            replacement_guard=repl,
        )
        fp.replacement_active = True
        fp.save()
        FixedPost.objects.filter(pk=fp.pk).update(
            updated_at=timezone.now() + timedelta(minutes=5)
        )
        kinds = {e["kind"] for e in build_activity_events(limit=200)}
        self.assertIn("fixed_post_replacement", kinds)
