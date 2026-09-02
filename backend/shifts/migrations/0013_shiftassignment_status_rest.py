# Roulement : titulaire en repos couvert par un RLT

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shifts", "0012_shiftassignment_status_roulement"),
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
                    ("rest", "Repos (roulement)"),
                    ("replaced", "Remplacé"),
                    ("completed", "Terminé"),
                    ("missed", "Manqué"),
                ],
                default="scheduled",
                max_length=16,
            ),
        ),
    ]
