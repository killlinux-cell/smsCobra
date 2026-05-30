from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_user_height_cm_education_level"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="id_document_verso",
            field=models.FileField(
                blank=True,
                help_text="Scan ou photo du verso de la pièce d'identité.",
                null=True,
                upload_to="id_documents/",
                verbose_name="Pièce d'identité — verso",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="id_document",
            field=models.FileField(
                blank=True,
                help_text="Scan ou photo du recto (face avant) de la pièce d'identité.",
                null=True,
                upload_to="id_documents/",
                verbose_name="Pièce d'identité — recto",
            ),
        ),
    ]
