from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("alerts", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="latealert",
            index=models.Index(fields=["assignment", "status"], name="latealert_asg_status_idx"),
        ),
        migrations.AddIndex(
            model_name="latealert",
            index=models.Index(fields=["status", "triggered_at"], name="latealert_status_time_idx"),
        ),
    ]
