from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_user_id_document_verso"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="face_embedding",
            field=models.JSONField(
                blank=True,
                null=True,
                help_text="Empreinte faciale 128D pré-calculée à partir de la photo portrait.",
            ),
        ),
    ]
