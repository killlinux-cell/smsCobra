from datetime import date, time, timedelta

from django.db import transaction

from .models import FixedPost, ShiftAssignment


def _slot_for(shift_type: str):
    if shift_type == FixedPost.ShiftType.DAY:
        return time(6, 0), time(18, 0)
    return time(18, 0), time(6, 0)


def _in_fixed_post_range(post: FixedPost, day: date) -> bool:
    if post.start_date and day < post.start_date:
        return False
    if post.end_date and day > post.end_date:
        return False
    return True


@transaction.atomic
def ensure_assignments_for_dates(days: list[date]) -> None:
    if not days:
        return
    unique_days = sorted(set(days))
    posts = (
        FixedPost.objects.select_related("site", "titular_guard", "replacement_guard")
        .filter(is_active=True)
        .order_by("site_id", "shift_type")
    )
    for day in unique_days:
        for post in posts:
            if not _in_fixed_post_range(post, day):
                continue
            start_time, end_time = _slot_for(post.shift_type)
            guard = post.current_guard
            defaults = {
                "guard": guard,
                "end_time": end_time,
                "status": ShiftAssignment.Status.REPLACED
                if post.replacement_active and post.replacement_guard_id
                else ShiftAssignment.Status.SCHEDULED,
                "original_guard": post.titular_guard
                if post.replacement_active and post.replacement_guard_id
                else None,
            }
            # Ne modifie pas une affectation existante (historique / ajustements manuels).
            ShiftAssignment.objects.get_or_create(
                site=post.site,
                shift_date=day,
                start_time=start_time,
                defaults=defaults,
            )

    # (Re)lier la passation jour -> nuit du même site.
    for day in unique_days:
        next_day = day + timedelta(days=1)
        day_rows = ShiftAssignment.objects.select_related("site").filter(
            shift_date=day,
            start_time=time(6, 0),
        )
        for row in day_rows:
            incoming = ShiftAssignment.objects.filter(
                site=row.site,
                shift_date=day,
                start_time=time(18, 0),
            ).first()
            if row.relieved_by_id != (incoming.id if incoming else None):
                row.relieved_by = incoming
                row.save(update_fields=["relieved_by"])

        night_rows = ShiftAssignment.objects.select_related("site").filter(
            shift_date=day,
            start_time=time(18, 0),
        )
        for row in night_rows:
            incoming = ShiftAssignment.objects.filter(
                site=row.site,
                shift_date=next_day,
                start_time=time(6, 0),
            ).first()
            if row.relieved_by_id != (incoming.id if incoming else None):
                row.relieved_by = incoming
                row.save(update_fields=["relieved_by"])
