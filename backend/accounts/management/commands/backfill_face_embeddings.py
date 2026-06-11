from django.core.management.base import BaseCommand

from accounts.face_profile import refresh_face_embedding_for_user
from accounts.models import User


class Command(BaseCommand):
    help = "Recalcule les empreintes faciales des vigiles à partir de leur photo portrait."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-missing",
            action="store_true",
            help="Ne traiter que les vigiles sans empreinte enregistrée.",
        )

    def handle(self, *args, **options):
        qs = User.objects.filter(role=User.Role.VIGILE).exclude(profile_photo="")
        if options["only_missing"]:
            qs = qs.filter(face_embedding__isnull=True)

        ok_count = 0
        fail_count = 0
        for user in qs.iterator():
            ok, fail = refresh_face_embedding_for_user(user)
            if ok:
                ok_count += 1
            else:
                fail_count += 1
                self.stdout.write(
                    self.style.WARNING(f"{user.username}: échec ({fail})")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Terminé — {ok_count} empreinte(s) enregistrée(s), {fail_count} échec(s)."
            )
        )
