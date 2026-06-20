"""Vigiles avec prise de service pointée mais fin de service non clôturée."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from django.db.models import Exists, OuterRef, Subquery
from django.utils import timezone

from checkins.models import Checkin
from shifts.models import ShiftAssignment
from shifts.serializers import ShiftAssignmentSerializer
from shifts.site_shift_times import shift_type_for_start_time


@dataclass
class OpenShiftRow:
    assignment: ShiftAssignment
    started_at: datetime | None
    slot_label: str
    end_block_reason: str | None
    can_end: bool
    is_stale: bool
    days_behind: int


def count_stale_open_shifts(*, today: date | None = None) -> int:
    """Postes ouverts dont la date planifiée est antérieure à aujourd'hui."""
    day = today or timezone.localdate()
    return _open_assignments_queryset(stale_only=True, today=day).count()


def collect_open_shift_rows(
    *,
    today: date | None = None,
    site_id: int | None = None,
    stale_only: bool = False,
) -> list[OpenShiftRow]:
    day = today or timezone.localdate()
    qs = _open_assignments_queryset(
        stale_only=stale_only,
        today=day,
        site_id=site_id,
    )
    rows: list[OpenShiftRow] = []
    for assignment in qs:
        started_at = (
            Checkin.objects.filter(assignment=assignment, type=Checkin.Type.START)
            .order_by("-timestamp")
            .values_list("timestamp", flat=True)
            .first()
        )
        ser = ShiftAssignmentSerializer(assignment)
        data = ser.data
        shift_type = shift_type_for_start_time(assignment.site, assignment.start_time)
        if shift_type == "day":
            slot = "Jour"
        elif shift_type == "night":
            slot = "Nuit"
        else:
            slot = f"{assignment.start_time.strftime('%H:%M')}–{assignment.end_time.strftime('%H:%M')}"
        days_behind = (day - assignment.shift_date).days
        rows.append(
            OpenShiftRow(
                assignment=assignment,
                started_at=started_at,
                slot_label=slot,
                end_block_reason=data.get("end_block_reason"),
                can_end=bool(data.get("can_end")),
                is_stale=assignment.shift_date < day,
                days_behind=max(0, days_behind),
            )
        )
    return rows


def _open_assignments_queryset(
    *,
    today: date,
    site_id: int | None = None,
    stale_only: bool = False,
):
    start_exists = Checkin.objects.filter(
        assignment_id=OuterRef("pk"),
        type=Checkin.Type.START,
    )
    end_exists = Checkin.objects.filter(
        assignment_id=OuterRef("pk"),
        type=Checkin.Type.END,
    )
    start_ts = (
        Checkin.objects.filter(
            assignment_id=OuterRef("pk"),
            type=Checkin.Type.START,
        )
        .order_by("-timestamp")
        .values("timestamp")[:1]
    )
    qs = (
        ShiftAssignment.objects.filter(Exists(start_exists))
        .exclude(Exists(end_exists))
        .annotate(started_at=Subquery(start_ts))
        .select_related("site", "guard", "relieved_by", "relieved_by__guard")
        .order_by("shift_date", "site__name", "start_time")
    )
    if stale_only:
        qs = qs.filter(shift_date__lt=today)
    if site_id:
        qs = qs.filter(site_id=site_id)
    return qs
