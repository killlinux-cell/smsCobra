import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("shifts", "0003_alter_shiftassignment_relieved_by"),
    ]

    operations = [
        migrations.AddField(
            model_name="shiftassignment",
            name="original_guard",
            field=models.ForeignKey(
                blank=True,
                help_text="Vigile titulaire d'origine lorsqu'un remplaçant a été désigné (dépêche).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assignments_as_original_titular",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
