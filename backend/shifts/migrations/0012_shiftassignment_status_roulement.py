# Generated manually for roulement MVP

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shifts", "0011_remove_fixedpost_uniq_active_fixedpost_per_site_shift_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="shiftassignment",
            name="status",
            field=models.CharField(
                choices=[
                    ("scheduled", "Planifié"),
                    ("extra", "Extra"),
                    ("roulement", "Roulement"),
                    ("replaced", "Remplacé"),
                    ("completed", "Terminé"),
                    ("missed", "Manqué"),
                ],
                default="scheduled",
                max_length=16,
            ),
        ),
    ]
