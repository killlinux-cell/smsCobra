from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from accounts.vigile_username_normalize import (
    is_standard_vigile_username,
    plan_vigile_username_normalizations,
)


class Command(BaseCommand):
    help = (
        "Rattrape les identifiants vigiles saisis manuellement (ex. 001, 002) "
        "en les renommant au format VIR-XXX, sans modifier l'application."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Appliquer les renommages (par défaut : simulation uniquement).",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        qs = User.objects.filter(role=User.Role.VIGILE).order_by("id")
        vigiles = [
            (uid, username)
            for uid, username in qs.values_list("id", "username")
            if not is_standard_vigile_username(username or "")
        ]

        if not vigiles:
            self.stdout.write(self.style.SUCCESS("Aucun identifiant vigile à normaliser."))
            return

        changes, warnings = plan_vigile_username_normalizations(vigiles)

        for msg in warnings:
            self.stdout.write(self.style.WARNING(msg))

        if not changes:
            self.stdout.write(
                self.style.SUCCESS("Rien à modifier après analyse des identifiants.")
            )
            return

        mode = "APPLICATION" if apply_changes else "SIMULATION"
        self.stdout.write(self.style.MIGRATE_HEADING(f"Mode {mode} — {len(changes)} vigile(s)"))
        for change in changes:
            self.stdout.write(
                f"  #{change.user_id}: {change.old_username!r} -> {change.new_username!r} "
                f"({change.reason})"
            )

        if not apply_changes:
            self.stdout.write(
                self.style.NOTICE(
                    "\nAucune modification en base. Relancez avec --apply pour enregistrer."
                )
            )
            return

        with transaction.atomic():
            for change in changes:
                User.objects.filter(pk=change.user_id).update(username=change.new_username)

        self.stdout.write(
            self.style.SUCCESS(f"{len(changes)} identifiant(s) vigile normalisé(s).")
        )
