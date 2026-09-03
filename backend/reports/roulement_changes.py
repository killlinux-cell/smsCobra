"""Trace des décisions roulement (planification manuelle par l'admin)."""

from __future__ import annotations

from datetime import date

from django.utils import timezone

from reports.models import AttendanceReport, RoulementChangeLog
from shifts.models import FixedPost, ShiftAssignment
from shifts.site_shift_times import SHIFT_DAY, SHIFT_NIGHT


def _guard_label(user) -> str:
    if not user:
        return "Vigile"
    return (user.get_full_name() or "").strip() or user.username


def _shift_label(shift_type: str) -> str:
    if shift_type == SHIFT_DAY:
        return "Jour"
    if shift_type == SHIFT_NIGHT:
        return "Nuit"
    return shift_type or "Créneau"


def _append_report_note(*, site_id: int, guard_id: int, report_date: date, line: str) -> None:
    if not site_id or not guard_id or not line:
        return
    report, _ = AttendanceReport.objects.get_or_create(
        site_id=site_id,
        guard_id=guard_id,
        report_date=report_date,
    )
    existing = (report.notes or "").strip()
    if line in existing:
        return
    report.notes = f"{existing}\n{line}".strip() if existing else line
    report.save(update_fields=["notes"])


def log_roulement_planned(
    *,
    assignment: ShiftAssignment,
    relieved_guard,
    shift_type: str,
    actor=None,
) -> RoulementChangeLog:
    ts = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")
    site = assignment.site
    site_name = site.name if site else "Site"
    rlt_name = _guard_label(assignment.guard)
    relieved_name = _guard_label(relieved_guard)
    shift_label = _shift_label(shift_type)
    day_label = assignment.shift_date.strftime("%d/%m/%Y")
    actor_name = _guard_label(actor) if actor else "Admin"

    detail = (
        f"[{ts}] {actor_name} : {rlt_name} planifié sur « {site_name} » "
        f"({shift_label} {day_label} {assignment.start_time:%H:%M}–{assignment.end_time:%H:%M}) "
        f"en remplacement de {relieved_name} (repos titulaire)."
    )

    if relieved_guard and site:
        _append_report_note(
            site_id=site.pk,
            guard_id=relieved_guard.pk,
            report_date=assignment.shift_date,
            line=f"[{ts}] En repos — couvert par {rlt_name} ({shift_label}).",
        )
        _append_report_note(
            site_id=site.pk,
            guard_id=assignment.guard_id,
            report_date=assignment.shift_date,
            line=f"[{ts}] Mission roulement — remplace {relieved_name} sur « {site_name} » ({shift_label}).",
        )

    return RoulementChangeLog.objects.create(
        kind=RoulementChangeLog.Kind.PLANNED,
        site=site,
        shift_date=assignment.shift_date,
        shift_type=shift_type,
        rlt_guard=assignment.guard,
        relieved_guard=relieved_guard,
        assignment=assignment,
        actor=actor,
        detail=detail,
    )


def log_roulement_cancelled(
    *,
    assignment: ShiftAssignment,
    actor=None,
) -> RoulementChangeLog:
    ts = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")
    site = assignment.site
    site_name = site.name if site else "Site"
    rlt_name = _guard_label(assignment.guard)
    relieved = assignment.original_guard
    relieved_name = _guard_label(relieved) if relieved else "—"
    actor_name = _guard_label(actor) if actor else "Admin"
    day_label = assignment.shift_date.strftime("%d/%m/%Y")

    detail = (
        f"[{ts}] {actor_name} : annulation mission {rlt_name} sur « {site_name} » "
        f"({day_label}). Titulaire reposé : {relieved_name}."
    )

    return RoulementChangeLog.objects.create(
        kind=RoulementChangeLog.Kind.CANCELLED,
        site=site,
        shift_date=assignment.shift_date,
        shift_type=_infer_shift_type(site, assignment.start_time),
        rlt_guard=assignment.guard,
        relieved_guard=relieved,
        assignment=None,
        actor=actor,
        detail=detail,
    )


def log_vigile_converted_to_rlt(*, vigile, actor=None) -> RoulementChangeLog:
    ts = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")
    actor_name = _guard_label(actor) if actor else "Admin"
    name = _guard_label(vigile)
    detail = f"[{ts}] {actor_name} : {name} converti en vigile roulement ({vigile.username})."
    return RoulementChangeLog.objects.create(
        kind=RoulementChangeLog.Kind.CONVERTED,
        rlt_guard=vigile,
        actor=actor,
        detail=detail,
    )


def _infer_shift_type(site, start_time) -> str:
    from shifts.site_shift_times import shift_type_for_start_time

    st = shift_type_for_start_time(site, start_time) if site and start_time else None
    return st or ""
