from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sites", "0003_geofence_gps_margin_and_distance"),
    ]

    operations = [
        migrations.AlterField(
            model_name="site",
            name="geofence_gps_margin_meters",
            field=models.PositiveSmallIntegerField(
                default=75,
                help_text=(
                    "Marge ajoutée au rayon pour l'imprécision GPS des téléphones (réduit les faux « hors zone »). "
                    "Mettre 0 pour un contrôle strict."
                ),
            ),
        ),
    ]
