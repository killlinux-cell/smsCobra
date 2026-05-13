from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("sites", "0004_alter_site_geofence_gps_margin_default"),
        ("shifts", "0005_shiftassignment_perf_indexes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FixedPost",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("shift_type", models.CharField(choices=[("day", "Jour (06:00-18:00)"), ("night", "Nuit (18:00-06:00)")], max_length=8)),
                ("replacement_active", models.BooleanField(default=False, help_text="Si activé, le remplaçant tient le poste de façon continue.")),
                ("is_active", models.BooleanField(default=True)),
                ("start_date", models.DateField(blank=True, null=True)),
                ("end_date", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("replacement_guard", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="replacement_fixed_posts", to=settings.AUTH_USER_MODEL)),
                ("site", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fixed_posts", to="sites.site")),
                ("titular_guard", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="titular_fixed_posts", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(
            model_name="fixedpost",
            index=models.Index(fields=["site", "shift_type", "is_active"], name="fxpost_site_shift_active_idx"),
        ),
        migrations.AddConstraint(
            model_name="fixedpost",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_active", True)),
                fields=("site", "shift_type"),
                name="uniq_active_fixedpost_per_site_shift",
            ),
        ),
    ]
