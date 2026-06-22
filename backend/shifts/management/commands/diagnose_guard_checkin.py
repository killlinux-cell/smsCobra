"""Diagnostic pointage vigile : affectations, postes ouverts, blocages."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from checkins.models import Checkin
from checkins.window import validate_start_window
from shifts.models import FixedPost, ShiftAssignment
from shifts.serializers import ShiftAssignmentSerializer
from shifts.services import ensure_assignments_for_dates

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Diagnostique les blocages de pointage pour un vigile (ex. VIR-005) : "
        "postes fixes, affectations hier/aujourd'hui, pointages, postes ouverts."
    )

    def add_arguments(self, parser):
        parser.add_argument("username", help="Username du vigile (ex. VIR-005)")
        parser.add_argument(
            "--ensure",
            action="store_true",
            help="Recréer les affectations planifiées manquantes pour hier/aujourd'hui.",
        )

    def handle(self, *args, **options):
        username = options["username"].strip()
        guard = User.objects.filter(username__iexact=username).first()
        if not guard:
            self.stderr.write(self.style.ERROR(f"Vigile introuvable : {username}"))
            return

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        if options["ensure"]:
            ensure_assignments_for_dates([yesterday, today])
            self.stdout.write(self.style.SUCCESS("ensure_assignments_for_dates exécuté."))

        self.stdout.write(self.style.MIGRATE_HEADING(f"Vigile {guard.username} (id={guard.pk})"))
        self._print_fixed_posts(guard)
        self._print_assignments(guard, yesterday, today)

    def _print_fixed_posts(self, guard):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Postes fixes"))
        posts = FixedPost.objects.filter(is_active=True).filter(
            models_q_titular_or_suspended(guard)
        ).select_related("site", "titular_guard", "suspended_titular_guard")
        if not posts:
            posts = FixedPost.objects.filter(
                models_q_titular_or_suspended(guard)
            ).select_related("site", "titular_guard", "suspended_titular_guard").order_by("-is_active")[:5]
        if not posts:
            self.stdout.write("  (aucun poste fixe lié)")
            return
        for post in posts:
            suspended = (
                post.suspended_titular_guard.username
                if post.suspended_titular_guard_id
                else "—"
            )
            self.stdout.write(
                f"  Poste #{post.pk} {post.site.name} ({post.get_shift_type_display()}) "
                f"actif={post.is_active} titulaire={post.titular_guard.username} "
                f"suspendu={suspended}"
            )

    def _print_assignments(self, guard, yesterday, today):
        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING(f"Affectations {yesterday.isoformat()} / {today.isoformat()}")
        )
        qs = (
            ShiftAssignment.objects.select_related("site", "guard")
            .filter(guard=guard, shift_date__in=[yesterday, today])
            .order_by("shift_date", "start_time")
        )
        if not qs.exists():
            self.stdout.write("  (aucune affectation hier/aujourd'hui)")
            return

        serializer = ShiftAssignmentSerializer()
        open_shifts = []
        for row in qs:
            data = serializer.to_representation(row)
            checkins = list(
                Checkin.objects.filter(assignment=row)
                .order_by("timestamp")
                .values_list("type", "timestamp", "guard_id")
            )
            ok_start, start_msg = validate_start_window(row)
            line = (
                f"  #{row.pk} {row.site.name} {row.shift_date} "
                f"{row.start_time:%H:%M}-{row.end_time:%H:%M} "
                f"status={row.status} has_start={data['has_start']} has_end={data['has_end']}"
            )
            self.stdout.write(line)
            if checkins:
                for ctype, ts, gid in checkins:
                    self.stdout.write(f"      pointage {ctype} @ {ts} (guard_id={gid})")
            else:
                self.stdout.write("      (aucun pointage)")
            if data["has_start"] and not data["has_end"]:
                open_shifts.append(row)
                self.stdout.write(self.style.WARNING("      >>> POSTE OUVERT (priorité app mobile)"))
            if not data["has_start"]:
                if ok_start:
                    self.stdout.write(self.style.SUCCESS("      prise de service : autorisée"))
                else:
                    self.stdout.write(self.style.ERROR(f"      prise bloquée : {start_msg}"))
            if data["end_block_reason"]:
                self.stdout.write(f"      fin : {data['end_block_reason']}")

        self.stdout.write("")
        if open_shifts:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(open_shifts)} poste(s) ouvert(s) : l'app affiche celui-ci en priorité. "
                    "Clôturer via dashboard « Services ouverts » ou "
                    "`close_stale_open_shifts --apply` si date antérieure."
                )
            )
        else:
            self.stdout.write("Aucun poste ouvert bloquant détecté pour ce vigile.")


def models_q_titular_or_suspended(guard):
    from django.db.models import Q

    return Q(titular_guard=guard) | Q(suspended_titular_guard=guard)
