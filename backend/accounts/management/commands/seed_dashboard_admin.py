from django.core.management.base import BaseCommand

from accounts.models import User

_DASHBOARD_ROLES = {
    User.Role.SUPER_ADMIN,
    User.Role.ADMIN_SOCIETE,
    User.Role.SUPERVISEUR,
}


class Command(BaseCommand):
    help = (
        "Crée ou met à jour un compte pour le tableau de bord /dashboard "
        "(rôle super_admin, mot de passe défini)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default="cobra",
            help="Nom d'utilisateur (défaut: cobra).",
        )
        parser.add_argument(
            "--password",
            default="cobra",
            help="Mot de passe (défaut: cobra). À changer en production.",
        )

    def handle(self, *args, **options):
        username = (options["username"] or "").strip()
        password = options["password"] or ""
        if not username or not password:
            self.stderr.write(self.style.ERROR("username et password requis."))
            return

        user = User.objects.filter(username=username).first()
        if user is None:
            user = User.objects.create_user(
                username=username,
                password=password,
                role=User.Role.SUPER_ADMIN,
                is_staff=True,
                is_superuser=True,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Compte créé : {username} (super_admin). Connexion : /dashboard/login/"
                )
            )
            return

        user.set_password(password)
        if user.role not in _DASHBOARD_ROLES:
            user.role = User.Role.SUPER_ADMIN
        user.is_staff = True
        user.is_superuser = True
        user.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"Compte mis à jour : {username} (mot de passe et droits dashboard). "
                "Connexion : /dashboard/login/"
            )
        )
