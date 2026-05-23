"""Affiche la traceback exacte si le tableau de bord plante (à lancer sur le VPS)."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.utils import timezone

from shifts.services import ensure_assignments_for_dates


class Command(BaseCommand):
    help = "Teste ensure_assignments, scan alertes et rendu /dashboard/ (diagnostic erreur 500)."

    def handle(self, *args, **options):
        today = timezone.localdate()
        days = [today, today + timedelta(days=1)]

        self.stdout.write("1/3 ensure_assignments_for_dates…")
        ensure_assignments_for_dates(days)
        self.stdout.write(self.style.SUCCESS("   OK"))

        self.stdout.write("2/3 detect_missed_shift_task…")
        from alerts.tasks import detect_missed_shift_task

        detect_missed_shift_task()
        self.stdout.write(self.style.SUCCESS("   OK"))

        self.stdout.write("3/3 dashboard_view…")
        from webadmin.views import dashboard_view

        User = get_user_model()
        user = (
            User.objects.filter(
                role__in=["super_admin", "admin_societe", "superviseur"],
                is_active=True,
            )
            .order_by("pk")
            .first()
        )
        if not user:
            self.stderr.write("Aucun compte admin/superviseur actif trouvé.")
            return

        request = RequestFactory().get("/dashboard/")
        request.user = user
        response = dashboard_view(request)
        self.stdout.write(
            self.style.SUCCESS(f"   OK — statut HTTP {response.status_code}")
        )
