from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_aval_date_integration_id_document"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="domicile",
            field=models.TextField(
                blank=True,
                help_text="Adresse ou lieu de résidence du vigile.",
            ),
        ),
    ]
