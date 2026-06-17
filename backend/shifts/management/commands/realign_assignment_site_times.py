from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date

from shifts.realign_assignment_times import (
    apply_realign_scheduled_assignment_times,
    plan_realign_scheduled_assignment_times,
)


class Command(BaseCommand):
    help = (
        "Recale les affectations planifiées futures encore en 06:00/18:00 fixes "
        "sur les horaires attendus de chaque site. "
        "Ne modifie jamais une affectation avec prise de service déjà pointée."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Appliquer les changements (par défaut : simulation).",
        )
        parser.add_argument(
            "--from-date",
            dest="from_date",
            default="",
            help="Date minimale AAAA-MM-JJ (défaut : aujourd'hui).",
        )
        parser.add_argument(
            "--site-id",
            dest="site_id",
            type=int,
            default=None,
            help="Limiter à un site (ID).",
        )

    def handle(self, *args, **options):
        from_date = timezone.localdate()
        if options["from_date"]:
            parsed = parse_date(options["from_date"])
            if not parsed:
                self.stderr.write(self.style.ERROR("Date invalide (--from-date)."))
                return
            from_date = parsed

        site_id = options.get("site_id")
        apply_changes = options["apply"]

        if apply_changes:
            with transaction.atomic():
                result = apply_realign_scheduled_assignment_times(
                    from_date=from_date,
                    site_id=site_id,
                )
        else:
            result = plan_realign_scheduled_assignment_times(
                from_date=from_date,
                site_id=site_id,
            )

        mode = "APPLICATION" if apply_changes else "SIMULATION"
        self.stdout.write(self.style.MIGRATE_HEADING(f"Mode {mode}"))
        self.stdout.write(f"  À partir du : {from_date.isoformat()}")
        if site_id:
            self.stdout.write(f"  Site ID     : {site_id}")
        self.stdout.write(f"  Candidats   : {len(result.candidates)}")
        self.stdout.write(f"  Ignorées (déjà pointées START) : {result.skipped_has_start}")
        self.stdout.write(f"  Ignorées (déjà correctes)      : {result.skipped_already_ok}")
        self.stdout.write(f"  Ignorées (autre créneau)       : {result.skipped_not_legacy}")
        self.stdout.write(f"  Ignorées (créneau inconnu)     : {result.skipped_unknown_slot}")

        for row in result.candidates[:200]:
            self.stdout.write(
                f"  #{row.assignment_id} {row.site_name} {row.shift_date} "
                f"{row.shift_type}: {row.old_start}-{row.old_end} -> "
                f"{row.new_start}-{row.new_end}"
            )
        if len(result.candidates) > 200:
            self.stdout.write(f"  … et {len(result.candidates) - 200} autre(s) ligne(s).")

        if apply_changes:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n{result.applied} affectation(s) recalée(s). "
                    f"Passations relinkées ({result.relieved_by_reset} relieved_by réinitialisés)."
                )
            )
        elif result.candidates:
            self.stdout.write(
                self.style.NOTICE(
                    "\nAucune modification. Relancez avec --apply pour enregistrer."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("\nRien à recaler."))
