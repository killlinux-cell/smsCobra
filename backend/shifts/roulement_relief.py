"""Repos titulaire couvert par une affectation roulement."""

from __future__ import annotations

from datetime import date, time

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from alerts.models import LateAlert
from shifts.models import FixedPost, ShiftAssignment
from sites.models import Site


def titulars_for_site_shift(site: Site, shift_type: str):
    """Titulaires actifs sur le site pour le créneau jour ou nuit."""
    return (
        User.objects.filter(
            pk__in=FixedPost.objects.filter(
                site=site,
                shift_type=shift_type,
                is_active=True,
                titular_guard_id__isnull=False,
            ).values_list("titular_guard_id", flat=True)
        )
        .order_by("first_name", "last_name", "username")
    )


def validate_relieved_titular(
    *,
    relieved_titular: User | None,
    site: Site,
    shift_type: str,
) -> None:
    if relieved_titular is None:
        return
    if relieved_titular.is_roulement:
        raise ValidationError("Le titulaire en repos ne peut pas être un vigile roulement (RLT).")
    allowed_ids = set(
        FixedPost.objects.filter(
            site=site,
            shift_type=shift_type,
            is_active=True,
        ).values_list("titular_guard_id", flat=True)
    )
    if relieved_titular.pk not in allowed_ids:
        raise ValidationError(
            f"{relieved_titular.display_name} n'est pas titulaire sur « {site.name} » "
            f"pour ce créneau ({shift_type})."
        )


def _resolve_open_alerts_for_assignment(assignment: ShiftAssignment) -> None:
    LateAlert.objects.filter(
        assignment=assignment,
        status__in=[LateAlert.Status.OPEN, LateAlert.Status.ACKNOWLEDGED],
    ).update(status=LateAlert.Status.RESOLVED, resolved_at=timezone.now())


@transaction.atomic
def mark_titular_relieved_by_roulement(
    *,
    relieved_titular: User,
    site: Site,
    shift_date: date,
    start_time: time,
    end_time: time,
) -> ShiftAssignment:
    """Passe l'affectation titulaire en repos (hors alertes) pour ce créneau."""
    titular_asg = (
        ShiftAssignment.objects.filter(
            guard=relieved_titular,
            site=site,
            shift_date=shift_date,
            start_time=start_time,
        )
        .exclude(status=ShiftAssignment.Status.EXTRA)
        .first()
    )
    if titular_asg:
        if titular_asg.status == ShiftAssignment.Status.ROULEMENT:
            raise ValidationError(
                f"{relieved_titular.username} a déjà une affectation roulement ce jour-là sur ce site."
            )
        if titular_asg.status not in (
            ShiftAssignment.Status.SCHEDULED,
            ShiftAssignment.Status.REST,
            ShiftAssignment.Status.REPLACED,
        ):
            raise ValidationError(
                f"Impossible de marquer {relieved_titular.username} en repos : "
                f"affectation déjà en cours ({titular_asg.get_status_display()})."
            )
        titular_asg.status = ShiftAssignment.Status.REST
        titular_asg.end_time = end_time
        titular_asg.save(update_fields=["status", "end_time"])
    else:
        titular_asg = ShiftAssignment.objects.create(
            guard=relieved_titular,
            site=site,
            shift_date=shift_date,
            start_time=start_time,
            end_time=end_time,
            status=ShiftAssignment.Status.REST,
        )
    _resolve_open_alerts_for_assignment(titular_asg)
    return titular_asg


@transaction.atomic
def restore_titular_after_roulement_cancel(roulement_assignment: ShiftAssignment) -> None:
    """Rétablit le titulaire en planifié si plus aucun RLT ne le couvre ce créneau."""
    from checkins.models import Checkin

    relieved_id = roulement_assignment.original_guard_id
    if not relieved_id:
        return
    still_covered = ShiftAssignment.objects.filter(
        status=ShiftAssignment.Status.ROULEMENT,
        site_id=roulement_assignment.site_id,
        shift_date=roulement_assignment.shift_date,
        start_time=roulement_assignment.start_time,
        original_guard_id=relieved_id,
    ).exclude(pk=roulement_assignment.pk).exists()
    if still_covered:
        return
    titular_asg = ShiftAssignment.objects.filter(
        guard_id=relieved_id,
        site_id=roulement_assignment.site_id,
        shift_date=roulement_assignment.shift_date,
        start_time=roulement_assignment.start_time,
        status=ShiftAssignment.Status.REST,
    ).first()
    if not titular_asg:
        return
    if Checkin.objects.filter(assignment=titular_asg).exists():
        return
    titular_asg.status = ShiftAssignment.Status.SCHEDULED
    titular_asg.save(update_fields=["status"])
