from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sites", "0006_backfill_site_created_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="site",
            name="site_manager_phone",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Téléphone du responsable sur place (contact opérationnel).",
                max_length=20,
                verbose_name="Numéro du responsable du site",
            ),
        ),
    ]
