from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from alerts.models import LateAlert
from shifts.models import FixedPost, ShiftAssignment
from shifts.roulement_assignment import create_roulement_assignments
from shifts.roulement_relief import restore_titular_after_roulement_cancel
from sites.models import Site

User = get_user_model()


class RoulementReliefTests(TestCase):
    def setUp(self):
        self.day = date(2026, 9, 1)
        self.site = Site.objects.create(
            name="Impérial Market",
            address="Abidjan",
            expected_start_time=time(8, 0),
            expected_end_time=time(20, 0),
            day_staff_required=0,
            night_staff_required=3,
            latitude=1,
            longitude=1,
        )
        self.tido = User.objects.create_user(username="VIR-143", password="x", role="vigile")
        self.soule = User.objects.create_user(username="VIR-097", password="x", role="vigile")
        self.kobenan = User.objects.create_user(username="VIR-081", password="x", role="vigile")
        self.rlt = User.objects.create_user(
            username="RLT-012",
            password="x",
            role="vigile",
            is_roulement=True,
            roulement_cycle_anchor=self.day,
        )
        for guard in (self.tido, self.soule, self.kobenan):
            FixedPost.objects.create(
                site=self.site,
                shift_type=FixedPost.ShiftType.NIGHT,
                titular_guard=guard,
                is_active=True,
            )
        night_start, night_end = time(20, 0), time(8, 0)
        for guard in (self.tido, self.soule, self.kobenan):
            ShiftAssignment.objects.create(
                guard=guard,
                site=self.site,
                shift_date=self.day,
                start_time=night_start,
                end_time=night_end,
                status=ShiftAssignment.Status.SCHEDULED,
            )

    def test_roulement_marks_titular_rest_and_excludes_from_active(self):
        rows = create_roulement_assignments(
            guard=self.rlt,
            site=self.site,
            shift_date=self.day,
            shift_type="night",
            relieved_titular=self.tido,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].original_guard_id, self.tido.id)
        tido_asg = ShiftAssignment.objects.get(guard=self.tido, shift_date=self.day)
        self.assertEqual(tido_asg.status, ShiftAssignment.Status.REST)
        active = ShiftAssignment.objects.filter(
            site=self.site,
            shift_date=self.day,
            status__in=ShiftAssignment.active_on_duty_statuses(),
        )
        self.assertEqual(active.count(), 3)

    def test_open_late_alert_closed_when_titular_marked_rest(self):
        tido_asg = ShiftAssignment.objects.get(guard=self.tido)
        LateAlert.objects.create(
            assignment=tido_asg,
            message=f"Retard prise de service : {self.tido.username} sur {self.site.name}",
        )
        create_roulement_assignments(
            guard=self.rlt,
            site=self.site,
            shift_date=self.day,
            shift_type="night",
            relieved_titular=self.tido,
        )
        tido_asg.refresh_from_db()
        self.assertEqual(tido_asg.status, ShiftAssignment.Status.REST)
        self.assertFalse(
            LateAlert.objects.filter(
                assignment=tido_asg,
                status=LateAlert.Status.OPEN,
            ).exists()
        )

    def test_cancel_roulement_restores_titular_scheduled(self):
        rows = create_roulement_assignments(
            guard=self.rlt,
            site=self.site,
            shift_date=self.day,
            shift_type="night",
            relieved_titular=self.tido,
        )
        restore_titular_after_roulement_cancel(rows[0])
        rows[0].delete()
        tido_asg = ShiftAssignment.objects.get(guard=self.tido, shift_date=self.day)
        self.assertEqual(tido_asg.status, ShiftAssignment.Status.SCHEDULED)

    def test_reject_non_titular_relieved(self):
        other = User.objects.create_user(username="VIR-999", password="x", role="vigile")
        with self.assertRaises(ValidationError):
            create_roulement_assignments(
                guard=self.rlt,
                site=self.site,
                shift_date=self.day,
                shift_type="night",
                relieved_titular=other,
            )
