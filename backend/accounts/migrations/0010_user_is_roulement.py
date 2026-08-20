# Generated manually for roulement MVP

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_controller_visit_default_visited_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_roulement",
            field=models.BooleanField(
                default=False,
                help_text="Vigile en roulement (RLT-) : couverture manuelle multi-sites, sans poste fixe titulaire.",
            ),
        ),
    ]
