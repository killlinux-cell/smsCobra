from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendancereport",
            name="was_absent",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Journée comptée absente : pas de prise de service, fin non pointée "
                    "après le créneau, ou fin avant l'heure prévue."
                ),
            ),
        ),
    ]
