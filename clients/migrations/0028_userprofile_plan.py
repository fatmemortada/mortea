from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0027_platformagreement"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="plan",
            field=models.CharField(
                choices=[
                    ("starter", "Starter"),
                    ("professional", "Professional"),
                    ("enterprise", "Enterprise"),
                ],
                default="starter",
                max_length=20,
            ),
        ),
    ]
