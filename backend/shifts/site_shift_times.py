"""Horaires jour/nuit dérivés des champs attendus du site."""

from __future__ import annotations

from datetime import date, time, timedelta

from shifts.models import FixedPost
from sites.models import Site

SHIFT_DAY = "day"
SHIFT_NIGHT = "night"

_LEGACY_DAY_START = time(6, 0)
_LEGACY_NIGHT_START = time(18, 0)


def day_slot_times(site: Site) -> tuple[time, time]:
    """Poste jour : prise et fin attendues du site."""
    return site.expected_start_time, site.expected_end_time


def night_slot_times(site: Site) -> tuple[time, time]:
    """Poste nuit : fin du jour → prise du lendemain."""
    return site.expected_end_time, site.expected_start_time


def _site_hours_cross_midnight(site: Site) -> bool:
    """True si les horaires attendus traversent minuit (ex. 19:00 → 07:00)."""
    return site.expected_start_time > site.expected_end_time


def _night_only_inverted_site(site: Site) -> bool:
    return (
        site.staff_required_for_shift(SHIFT_DAY) == 0
        and site.staff_required_for_shift(SHIFT_NIGHT) > 0
        and _site_hours_cross_midnight(site)
    )


def _day_only_site(site: Site) -> bool:
    return (
        site.staff_required_for_shift(SHIFT_NIGHT) == 0
        and site.staff_required_for_shift(SHIFT_DAY) > 0
    )


def slot_times_for_site(site: Site, shift_type: str) -> tuple[time, time]:
    day_start, day_end = day_slot_times(site)
    night_start, night_end = night_slot_times(site)
    # Site nuit-seule avec horaires 19h→7h : le poste « nuit » = horaires attendus du site.
    if _night_only_inverted_site(site) and shift_type in (
        FixedPost.ShiftType.NIGHT,
        SHIFT_NIGHT,
    ):
        return day_start, day_end
    if shift_type in (FixedPost.ShiftType.DAY, SHIFT_DAY):
        return day_start, day_end
    return night_start, night_end


def shift_type_for_start_time(site: Site, start_time: time) -> str | None:
    day_start, _ = day_slot_times(site)
    night_start, _ = night_slot_times(site)
    if _night_only_inverted_site(site):
        if start_time == day_start:
            return FixedPost.ShiftType.NIGHT
        return None
    if start_time == day_start:
        return FixedPost.ShiftType.DAY
    if start_time == night_start:
        return FixedPost.ShiftType.NIGHT
    # Anciennes affectations créées en 06:00 / 18:00 fixes
    if start_time == _LEGACY_DAY_START:
        return FixedPost.ShiftType.DAY
    if start_time == _LEGACY_NIGHT_START:
        return FixedPost.ShiftType.NIGHT
    return None


def assignment_is_operational(assignment) -> bool:
    """
    True si l'affectation correspond à un créneau actif du site (effectif cible > 0)
    et à l'heure canonique de ce créneau.
    """
    site = assignment.site
    shift_type = shift_type_for_start_time(site, assignment.start_time)
    if not shift_type or site.staff_required_for_shift(shift_type) <= 0:
        return False
    expected_start, _ = slot_times_for_site(site, shift_type)
    return assignment.start_time == expected_start


def incoming_relief_lookup(
    site: Site, shift_type: str, shift_date: date
) -> tuple[date, time]:
    """Date + heure de début du créneau de relève lié (passation)."""
    if _night_only_inverted_site(site):
        return shift_date, day_slot_times(site)[0]
    if shift_type in (FixedPost.ShiftType.DAY, SHIFT_DAY):
        night_start, _ = night_slot_times(site)
        return shift_date, night_start
    day_start, _ = day_slot_times(site)
    return shift_date + timedelta(days=1), day_start


def opposite_passation_slot(
    site: Site, shift_type: str, shift_date: date
) -> tuple[date, time]:
    """Créneau opposé (conflit vigile jour+nuit consécutifs)."""
    if shift_type in (FixedPost.ShiftType.DAY, SHIFT_DAY):
        night_start, _ = night_slot_times(site)
        return shift_date - timedelta(days=1), night_start
    day_start, _ = day_slot_times(site)
    return shift_date + timedelta(days=1), day_start


def slot_label(site: Site, shift_type: str) -> str:
    start, end = slot_times_for_site(site, shift_type)
    if shift_type in (FixedPost.ShiftType.NIGHT, SHIFT_NIGHT):
        return f"Nuit ({start.strftime('%H:%M')}-{end.strftime('%H:%M')})"
    return f"Jour ({start.strftime('%H:%M')}-{end.strftime('%H:%M')})"
