from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("shifts", "0007_activity_feed_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="fixedpost",
            name="suspended_titular_guard",
            field=models.ForeignKey(
                blank=True,
                help_text="Titulaire d'origine suspendu après dépêche ; repositionné par le superviseur.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="suspended_from_fixed_posts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="fixedpost",
            name="suspension_reason",
            field=models.TextField(
                blank=True,
                help_text="Motif de réintégration ou justification de l'absence (saisi par le superviseur).",
            ),
        ),
        migrations.AddField(
            model_name="fixedpost",
            name="suspended_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Date de suspension du titulaire d'origine (dépêche / absence).",
                null=True,
            ),
        ),
    ]
