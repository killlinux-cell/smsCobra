from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shifts", "0004_shiftassignment_original_guard"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="shiftassignment",
            index=models.Index(
                fields=["site", "shift_date", "status"],
                name="shift_site_date_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="shiftassignment",
            index=models.Index(
                fields=["guard", "shift_date", "status"],
                name="shift_guard_date_status_idx",
            ),
        ),
    ]
