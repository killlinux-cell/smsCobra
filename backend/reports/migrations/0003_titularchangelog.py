from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0002_attendancereport_was_absent"),
        ("shifts", "0008_fixedpost_suspended_titular"),
        ("sites", "0008_site_latitude_longitude_optional"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TitularChangeLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("titular_promoted", "Promotion titulaire"),
                            ("titular_reinstated", "Réintégration titulaire"),
                        ],
                        max_length=32,
                    ),
                ),
                ("shift_type", models.CharField(blank=True, max_length=8)),
                ("reason", models.TextField(blank=True)),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="titular_changes_as_actor",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "assignment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="titular_change_logs",
                        to="shifts.shiftassignment",
                    ),
                ),
                (
                    "fixed_post",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="titular_change_logs",
                        to="shifts.fixedpost",
                    ),
                ),
                (
                    "from_guard",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="titular_changes_from",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="titular_change_logs",
                        to="sites.site",
                    ),
                ),
                (
                    "to_guard",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="titular_changes_to",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-occurred_at"],
                "indexes": [
                    models.Index(fields=["site", "occurred_at"], name="titular_chg_site_time_idx")
                ],
            },
        ),
    ]
