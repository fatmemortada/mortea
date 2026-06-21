from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0025_compliancetask'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='subscription_active',
            field=models.BooleanField(default=False),
        ),
    ]
