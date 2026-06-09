"""Rôles affichés sur la fiche site (postes fixes + affectations)."""

from __future__ import annotations

from datetime import date

from shifts.models import FixedPost, ShiftAssignment


def _slot_label(start_time) -> str:
    if start_time is None:
        return "créneau"
    if start_time.hour == 6 and start_time.minute == 0:
        return "jour"
    if start_time.hour == 18 and start_time.minute == 0:
        return "nuit"
    return start_time.strftime("%H:%M")


def _fixed_post_slot_label(fp: FixedPost) -> str:
    if fp.shift_type == FixedPost.ShiftType.DAY:
        return "jour"
    if fp.shift_type == FixedPost.ShiftType.NIGHT:
        return "nuit"
    return fp.get_shift_type_display().lower()


def fixed_post_slots_covered(fixed_posts) -> set[tuple[int, str]]:
    """(guard_id, jour|nuit) déjà couverts par un poste fixe."""
    covered: set[tuple[int, str]] = set()
    for fp in fixed_posts:
        lab = _fixed_post_slot_label(fp)
        if fp.titular_guard_id:
            covered.add((fp.titular_guard_id, lab))
        if fp.suspended_titular_guard_id:
            covered.add((fp.suspended_titular_guard_id, lab))
        if fp.replacement_guard_id and fp.replacement_active:
            covered.add((fp.replacement_guard_id, lab))
    return covered


def enrich_guard_roles_from_assignments(
    fixed_posts,
    assignments_qs,
    *,
    today: date,
    note_role,
) -> None:
    """
    Complète les rôles affichés : dépêche, extra, en poste aujourd'hui.

    ``note_role`` : callable (user, label: str) -> None
    """
    covered = fixed_post_slots_covered(fixed_posts)
    active_statuses = set(ShiftAssignment.active_on_duty_statuses())

    for assignment in assignments_qs.iterator(chunk_size=200):
        guard = assignment.guard
        if guard is None:
            continue
        lab = _slot_label(assignment.start_time)
        slot_key = (guard.id, lab)

        if assignment.shift_date == today:
            if assignment.status == ShiftAssignment.Status.EXTRA:
                note_role(guard, f"Extra — {lab}")
            elif (
                assignment.status == ShiftAssignment.Status.REPLACED
                and assignment.original_guard_id
            ):
                note_role(guard, f"Dépêche — {lab}")
            elif assignment.status in active_statuses and slot_key not in covered:
                note_role(guard, f"En poste aujourd'hui — {lab}")
        elif (
            assignment.shift_date > today
            and assignment.status == ShiftAssignment.Status.EXTRA
        ):
            note_role(guard, f"Extra planifié — {lab}")


def sort_role_labels(roles: list[str]) -> list[str]:
    priority = (
        "Titulaire —",
        "Titulaire suspendu —",
        "Remplaçant en poste —",
        "Remplaçant désigné —",
        "Dépêche —",
        "Extra —",
        "Extra planifié —",
        "En poste aujourd'hui —",
    )

    def key(label: str) -> tuple[int, str]:
        for idx, prefix in enumerate(priority):
            if label.startswith(prefix):
                return (idx, label)
        return (len(priority), label)

    return sorted(roles, key=key)
