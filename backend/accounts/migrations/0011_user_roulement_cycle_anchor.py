# Roulement phase 2 — ancrage cycle 6j/1 repos

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_user_is_roulement"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="roulement_cycle_anchor",
            field=models.DateField(
                blank=True,
                null=True,
                help_text="Premier jour d'un bloc de service (cycle 6 jours + 1 repos).",
            ),
        ),
    ]
