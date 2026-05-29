from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sites", "0009_site_day_staff_required_site_night_staff_required"),
    ]

    operations = [
        migrations.AddField(
            model_name="site",
            name="site_manager_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Nom du responsable sur place (contact opérationnel).",
                max_length=200,
                verbose_name="Nom du responsable du site",
            ),
        ),
        migrations.AddField(
            model_name="site",
            name="site_sms_phone",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Numéro SMS du site (alertes ou contact opérationnel).",
                max_length=20,
                verbose_name="Numéro SMS du site",
            ),
        ),
    ]
