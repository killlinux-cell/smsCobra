# Journal des décisions roulement (admin)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0004_alter_titularchangelog_kind"),
        ("shifts", "0013_shiftassignment_status_rest"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("sites", "0011_alter_site_site_manager_phone"),
    ]

    operations = [
        migrations.CreateModel(
            name="RoulementChangeLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("roulement_planned", "Mission roulement planifiée"),
                            ("roulement_cancelled", "Mission roulement annulée"),
                            ("vigile_converted_rlt", "Conversion VIR → RLT"),
                        ],
                        max_length=32,
                    ),
                ),
                ("shift_date", models.DateField(blank=True, null=True)),
                ("shift_type", models.CharField(blank=True, max_length=8)),
                ("detail", models.TextField(blank=True)),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="roulement_changes_as_actor",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "assignment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="roulement_change_logs",
                        to="shifts.shiftassignment",
                    ),
                ),
                (
                    "relieved_guard",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="roulement_logs_relieved",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "rlt_guard",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="roulement_logs_as_rlt",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="roulement_change_logs",
                        to="sites.site",
                    ),
                ),
            ],
            options={
                "ordering": ["-occurred_at"],
                "indexes": [
                    models.Index(fields=["site", "occurred_at"], name="rlt_chg_site_time_idx"),
                ],
            },
        ),
    ]
