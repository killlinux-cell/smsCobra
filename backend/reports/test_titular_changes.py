from datetime import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from reports.activity_feed import build_activity_events
from reports.models import AttendanceReport, TitularChangeLog
from reports.titular_changes import log_titular_promotion, log_titular_reinstatement
from shifts.models import FixedPost, ShiftAssignment
from sites.models import Site

User = get_user_model()


class TitularChangeReportTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="sup1",
            password="x",
            role=User.Role.SUPERVISEUR,
            first_name="Sup",
            last_name="One",
        )
        self.titular = User.objects.create_user(username="tit", password="x", role=User.Role.VIGILE)
        self.replacement = User.objects.create_user(username="rep", password="x", role=User.Role.VIGILE)
        self.site = Site.objects.create(
            name="Plateau",
            address="A",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=1,
            longitude=1,
        )
        self.post = FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.replacement,
            suspended_titular_guard=self.titular,
            is_active=True,
        )
        self.assignment = ShiftAssignment.objects.create(
            guard=self.replacement,
            site=self.site,
            shift_date=timezone.localdate(),
            start_time=time(6, 0),
            end_time=time(18, 0),
            status=ShiftAssignment.Status.REPLACED,
            original_guard=self.titular,
        )

    def test_promotion_logs_notes_and_activity(self):
        log_titular_promotion(
            fixed_post=self.post,
            assignment=self.assignment,
            absent_guard=self.titular,
            new_titular_guard=self.replacement,
            actor=self.admin,
        )
        note_tit = AttendanceReport.objects.get(
            site=self.site, guard=self.titular, report_date=self.assignment.shift_date
        )
        self.assertIn("suspendu", note_tit.notes.lower())
        note_rep = AttendanceReport.objects.get(
            site=self.site, guard=self.replacement, report_date=self.assignment.shift_date
        )
        self.assertIn("promu titulaire", note_rep.notes.lower())

        events = build_activity_events(limit=50)
        kinds = [e["kind"] for e in events]
        self.assertIn("titular_promoted", kinds)

    def test_reinstatement_logs_notes_and_activity(self):
        log_titular_reinstatement(
            fixed_post=self.post,
            reinstated_guard=self.titular,
            former_titular_guard=self.replacement,
            reason="Certificat médical validé par le superviseur.",
            actor=self.admin,
        )
        note = AttendanceReport.objects.get(
            site=self.site, guard=self.titular, report_date=timezone.localdate()
        )
        self.assertIn("réintégré", note.notes.lower())
        self.assertEqual(TitularChangeLog.objects.filter(kind="titular_reinstated").count(), 1)

        events = build_activity_events(limit=50)
        self.assertTrue(any(e["kind"] == "titular_reinstated" for e in events))
