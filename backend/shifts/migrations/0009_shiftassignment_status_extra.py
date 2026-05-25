# Statut « extra » : choix TextChoices uniquement (valeur char inchangée).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shifts", "0008_fixedpost_suspended_titular"),
    ]

    operations = [
        migrations.AlterField(
            model_name="shiftassignment",
            name="status",
            field=models.CharField(
                choices=[
                    ("scheduled", "Planifié"),
                    ("extra", "Extra"),
                    ("replaced", "Remplacé"),
                    ("completed", "Terminé"),
                    ("missed", "Manqué"),
                ],
                default="scheduled",
                max_length=16,
            ),
        ),
    ]
