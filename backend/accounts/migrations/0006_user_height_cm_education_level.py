from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_alter_user_role_controllersiteassignment_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="height_cm",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Taille du vigile en centimètres.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="education_level",
            field=models.CharField(
                blank=True,
                choices=[
                    ("non_scolarise", "Non scolarisé"),
                    ("primaire", "Primaire"),
                    ("secondaire", "Secondaire / collège"),
                    ("bepc", "BEPC"),
                    ("bac", "Baccalauréat"),
                    ("bac_2", "BAC+2 (BTS, DUT…)"),
                    ("licence", "Licence (BAC+3)"),
                    ("master", "Master (BAC+5)"),
                    ("doctorat", "Doctorat"),
                    ("autre", "Autre"),
                ],
                help_text="Niveau d'études ou diplôme le plus élevé.",
                max_length=32,
            ),
        ),
    ]
