from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0014_userprofile_stripe_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
