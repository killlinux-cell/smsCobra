from django.core.management.base import BaseCommand
from django.utils import timezone

from checkins.models import Checkin
from reports.attendance import refresh_attendance_report
from shifts.models import ShiftAssignment
from webadmin.admin_force_end import stale_open_assignments


class Command(BaseCommand):
    help = (
        "Recalcule was_absent sur les rapports de pointage "
        "(ex. prise sans fin après la fin du créneau)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--site-id",
            dest="site_id",
            type=int,
            default=None,
            help="Limiter à un site (ID).",
        )

    def handle(self, *args, **options):
        today = timezone.localdate()
        site_id = options.get("site_id")
        qs = ShiftAssignment.objects.filter(shift_date__lte=today).select_related(
            "site", "guard"
        )
        if site_id:
            qs = qs.filter(site_id=site_id)

        updated = 0
        for assignment in qs.iterator(chunk_size=300):
            has_start = Checkin.objects.filter(
                assignment=assignment, type=Checkin.Type.START
            ).exists()
            if not has_start:
                continue
            before = refresh_attendance_report(assignment)
            updated += 1
            self.stdout.write(
                f"  #{assignment.id} {assignment.shift_date} {assignment.guard.username} "
                f"was_absent={before.was_absent}"
            )

        stale = stale_open_assignments(today=today, site_id=site_id).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{updated} rapport(s) recalculé(s). "
                f"{stale} poste(s) encore ouvert(s) sans fin."
            )
        )
