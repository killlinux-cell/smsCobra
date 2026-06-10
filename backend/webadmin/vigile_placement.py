"""Sites et postes actuels d'un vigile (fiche détail)."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from shifts.models import FixedPost, ShiftAssignment


def _shift_label_from_time(start_time) -> str:
    if start_time is None:
        return "Créneau"
    if start_time.hour == 6 and start_time.minute == 0:
        return "Jour (06h–18h)"
    if start_time.hour == 18 and start_time.minute == 0:
        return "Nuit (18h–06h)"
    return start_time.strftime("%H:%M")


def build_vigile_placement(vigile: User) -> dict:
    today = timezone.localdate()
    horizon = today + timedelta(days=30)
    placements: list[dict] = []
    seen: set[tuple] = set()
    fixed_slots: set[tuple[int, str]] = set()

    def add(
        *,
        site_id: int,
        site_name: str,
        role: str,
        shift_label: str,
        variant: str,
        detail: str = "",
    ) -> None:
        key = (site_id, shift_label, role)
        if key in seen:
            return
        seen.add(key)
        placements.append(
            {
                "site_id": site_id,
                "site_name": site_name,
                "role": role,
                "shift_label": shift_label,
                "variant": variant,
                "detail": detail,
            }
        )

    fixed_posts = (
        FixedPost.objects.filter(is_active=True)
        .select_related(
            "site",
            "titular_guard",
            "replacement_guard",
            "suspended_titular_guard",
        )
        .filter(
            Q(titular_guard=vigile)
            | Q(replacement_guard=vigile)
            | Q(suspended_titular_guard=vigile)
        )
        .order_by("site__name", "shift_type")
    )

    for fp in fixed_posts:
        site_name = fp.site.name if fp.site_id else "Site"
        shift_label = fp.get_shift_type_display()
        if fp.titular_guard_id == vigile.pk:
            fixed_slots.add((fp.site_id, fp.shift_type))
            add(
                site_id=fp.site_id,
                site_name=site_name,
                role="Titulaire en poste",
                shift_label=shift_label,
                variant="primary",
            )
        elif fp.suspended_titular_guard_id == vigile.pk:
            fixed_slots.add((fp.site_id, fp.shift_type))
            interim = (
                fp.titular_guard.display_name if fp.titular_guard_id else "—"
            )
            add(
                site_id=fp.site_id,
                site_name=site_name,
                role="Titulaire suspendu",
                shift_label=shift_label,
                variant="warning",
                detail=f"Intérim : {interim}",
            )
        elif fp.replacement_guard_id == vigile.pk and fp.replacement_active:
            fixed_slots.add((fp.site_id, fp.shift_type))
            tit = fp.titular_guard.display_name if fp.titular_guard_id else "—"
            add(
                site_id=fp.site_id,
                site_name=site_name,
                role="Remplaçant actif",
                shift_label=shift_label,
                variant="info",
                detail=f"Pour {tit}",
            )
        elif fp.replacement_guard_id == vigile.pk:
            add(
                site_id=fp.site_id,
                site_name=site_name,
                role="Remplaçant désigné",
                shift_label=shift_label,
                variant="secondary",
                detail=(
                    f"Titulaire : {fp.titular_guard.display_name}"
                    if fp.titular_guard_id
                    else ""
                ),
            )

    today_assignments = (
        ShiftAssignment.objects.filter(
            shift_date=today,
            guard=vigile,
            status__in=ShiftAssignment.active_on_duty_statuses(),
        )
        .select_related("site", "original_guard")
        .order_by("site__name", "start_time")
    )
    for assignment in today_assignments:
        shift_label = _shift_label_from_time(assignment.start_time)
        slot = (
            assignment.site_id,
            FixedPost.ShiftType.DAY
            if assignment.start_time.hour == 6
            else FixedPost.ShiftType.NIGHT
            if assignment.start_time.hour == 18
            else "",
        )
        if slot[1] and slot in fixed_slots:
            continue
        if assignment.status == ShiftAssignment.Status.EXTRA:
            role = "Extra"
            detail = ""
            variant = "info"
        elif (
            assignment.status == ShiftAssignment.Status.REPLACED
            and assignment.original_guard_id
        ):
            role = "Remplaçant dépêche"
            detail = f"Pour {assignment.original_guard.display_name}"
            variant = "success"
        else:
            role = "En poste aujourd'hui"
            detail = ""
            variant = "success"
        add(
            site_id=assignment.site_id,
            site_name=assignment.site.name,
            role=role,
            shift_label=shift_label,
            variant=variant,
            detail=detail,
        )

    upcoming: list[dict] = []
    if not placements:
        for assignment in (
            ShiftAssignment.objects.filter(
                guard=vigile,
                shift_date__gt=today,
                shift_date__lte=horizon,
                status=ShiftAssignment.Status.SCHEDULED,
            )
            .select_related("site")
            .order_by("shift_date", "start_time")[:5]
        ):
            upcoming.append(
                {
                    "site_id": assignment.site_id,
                    "site_name": assignment.site.name,
                    "shift_date": assignment.shift_date,
                    "shift_label": _shift_label_from_time(assignment.start_time),
                }
            )

    is_posted = bool(placements)
    distinct_sites: list[dict] = []
    seen_site_ids: set[int] = set()
    for row in placements:
        site_id = row["site_id"]
        if site_id in seen_site_ids:
            continue
        seen_site_ids.add(site_id)
        distinct_sites.append(
            {"site_id": site_id, "site_name": row["site_name"]}
        )

    return {
        "placements": placements,
        "distinct_sites": distinct_sites,
        "distinct_site_count": len(distinct_sites),
        "upcoming": upcoming,
        "is_posted": is_posted,
        "today": today,
    }
