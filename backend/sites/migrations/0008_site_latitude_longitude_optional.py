from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sites", "0007_site_site_manager_phone"),
    ]

    operations = [
        migrations.AlterField(
            model_name="site",
            name="latitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                help_text="Optionnel : sans coordonnées, la géofence au pointage est désactivée.",
                max_digits=9,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="site",
            name="longitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
            ),
        ),
    ]
