from datetime import date, time

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from reports.models import RoulementChangeLog
from shifts.models import FixedPost
from shifts.roulement_assignment import create_roulement_assignments
from sites.models import Site

User = get_user_model()


class RoulementAuditTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="ADM-01",
            password="x",
            role="super_admin",
        )
        self.day = date(2026, 9, 5)
        self.site = Site.objects.create(
            name="Impérial",
            address="Abidjan",
            expected_start_time=time(8, 0),
            expected_end_time=time(20, 0),
            day_staff_required=0,
            night_staff_required=1,
            latitude=5.3,
            longitude=-4.0,
        )
        self.tido = User.objects.create_user(username="VIR-143", password="x", role="vigile")
        self.rlt = User.objects.create_user(
            username="RLT-012",
            password="x",
            role="vigile",
            is_roulement=True,
            roulement_cycle_anchor=self.day,
        )
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.NIGHT,
            titular_guard=self.tido,
            is_active=True,
        )

    def test_plan_requires_relieved_titular(self):
        with self.assertRaises(ValidationError):
            create_roulement_assignments(
                guard=self.rlt,
                site=self.site,
                shift_date=self.day,
                shift_type="night",
            )

    def test_plan_creates_audit_log(self):
        rows = create_roulement_assignments(
            guard=self.rlt,
            site=self.site,
            shift_date=self.day,
            shift_type="night",
            relieved_titular=self.tido,
            actor=self.admin,
        )
        self.assertEqual(len(rows), 1)
        logs = RoulementChangeLog.objects.filter(kind=RoulementChangeLog.Kind.PLANNED)
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.rlt_guard_id, self.rlt.id)
        self.assertEqual(log.relieved_guard_id, self.tido.id)
        self.assertEqual(log.actor_id, self.admin.id)
        self.assertIn("VIR-143", log.detail)
        self.assertIn("RLT-012", log.detail)

    def test_assignment_links_relieved_titular(self):
        rows = create_roulement_assignments(
            guard=self.rlt,
            site=self.site,
            shift_date=self.day,
            shift_type="night",
            relieved_titular=self.tido,
            actor=self.admin,
        )
        self.assertEqual(rows[0].original_guard_id, self.tido.id)
