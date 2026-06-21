from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0017_corporate_lead'),
    ]

    operations = [
        migrations.AddField(
            model_name='corporatelead',
            name='authorized_representative_address',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='corporatelead',
            name='authorized_representative_email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name='corporatelead',
            name='authorized_representative_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='corporatelead',
            name='authorized_representative_phone',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name='corporatelead',
            name='officers',
            field=models.TextField(blank=True),
        ),
    ]
