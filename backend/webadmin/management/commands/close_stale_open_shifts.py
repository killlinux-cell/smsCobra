from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounts.models import User
from webadmin.admin_force_end import bulk_force_end_stale_open_shifts

DEFAULT_REASON = (
    "Alignement superviseur — clôture des postes antérieurs laissés ouverts "
    "(relève absente ou fin non pointée)."
)


class Command(BaseCommand):
    help = (
        "Clôture les affectations antérieures à aujourd'hui avec prise de service "
        "pointée mais sans fin (hors postes du jour). "
        "Simulation par défaut ; --apply pour enregistrer."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Enregistrer les fins de service (défaut : liste seulement).",
        )
        parser.add_argument(
            "--before-date",
            dest="before_date",
            default="",
            help="Date frontière AAAA-MM-JJ : clôturer shift_date < cette date "
            "(défaut : aujourd'hui, donc tout sauf le jour courant).",
        )
        parser.add_argument(
            "--site-id",
            dest="site_id",
            type=int,
            default=None,
            help="Limiter à un site (ID).",
        )
        parser.add_argument(
            "--reason",
            default=DEFAULT_REASON,
            help="Motif tracé dans les rapports de pointage.",
        )
        parser.add_argument(
            "--actor",
            default="",
            help="Username admin/superviseur pour la trace (défaut : premier admin_societe).",
        )

    def handle(self, *args, **options):
        today = timezone.localdate()
        if options["before_date"]:
            parsed = parse_date(options["before_date"])
            if not parsed:
                self.stderr.write(self.style.ERROR("Date invalide (--before-date)."))
                return
            today = parsed

        actor = self._resolve_actor(options["actor"].strip())
        site_id = options.get("site_id")
        apply = options["apply"]
        reason = (options["reason"] or DEFAULT_REASON).strip()

        result = bulk_force_end_stale_open_shifts(
            actor=actor,
            reason=reason,
            site_id=site_id,
            today=today,
            apply=apply,
        )
        candidates = result["candidates"]
        mode = "APPLICATION" if apply else "SIMULATION"

        self.stdout.write(self.style.MIGRATE_HEADING(f"Mode {mode}"))
        self.stdout.write(
            f"  Postes ouverts à clôturer (date < {today.isoformat()}) : {len(candidates)}"
        )
        if site_id:
            self.stdout.write(f"  Site ID : {site_id}")
        if actor:
            self.stdout.write(f"  Acteur  : {actor.username}")

        for assignment in candidates[:200]:
            self.stdout.write(
                f"  #{assignment.id} {assignment.shift_date} "
                f"{assignment.guard.username} @ {assignment.site.name} "
                f"{assignment.start_time.strftime('%H:%M')}-"
                f"{assignment.end_time.strftime('%H:%M')}"
            )
        if len(candidates) > 200:
            self.stdout.write(f"  … et {len(candidates) - 200} autre(s).")

        if apply:
            self.stdout.write(
                self.style.SUCCESS(f"\n{result['applied']} poste(s) clôturé(s).")
            )
            for aid, msg in result["errors"]:
                self.stderr.write(self.style.WARNING(f"  Ignoré #{aid} : {msg}"))
        elif candidates:
            self.stdout.write(
                self.style.NOTICE("\nAucune modification. Relancez avec --apply.")
            )
        else:
            self.stdout.write(self.style.SUCCESS("\nRien à clôturer."))

    def _resolve_actor(self, username: str):
        if username:
            return User.objects.filter(username=username).first()
        return (
            User.objects.filter(role=User.Role.ADMIN_SOCIETE, is_active=True)
            .order_by("id")
            .first()
            or User.objects.filter(is_superuser=True, is_active=True).order_by("id").first()
        )
