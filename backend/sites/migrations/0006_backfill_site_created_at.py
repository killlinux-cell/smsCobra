from django.db import migrations, models
from django.utils import timezone


def backfill_site_created_at(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    now = timezone.now()
    Site.objects.filter(created_at__isnull=True).update(created_at=now)


class Migration(migrations.Migration):
    dependencies = [
        ("sites", "0005_activity_feed_fields"),
    ]

    operations = [
        migrations.RunPython(backfill_site_created_at, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="site",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
