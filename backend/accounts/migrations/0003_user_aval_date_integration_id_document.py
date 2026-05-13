# Generated manually for vigile registration (web + API).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_user_profile_photo"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="aval",
            field=models.CharField(
                blank=True,
                help_text="Champ Aval (référence ou mention interne).",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="date_integration",
            field=models.DateField(
                blank=True,
                help_text="Date d'intégration du vigile.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="id_document",
            field=models.FileField(
                blank=True,
                help_text="Scan de la pièce d'identité (image ou PDF), via scanner ou fichier.",
                null=True,
                upload_to="id_documents/",
            ),
        ),
    ]
