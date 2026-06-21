from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0016_corporate_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='CorporateLead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('email', models.EmailField(max_length=254)),
                ('phone', models.CharField(blank=True, max_length=30)),
                ('company_type', models.CharField(choices=[('named', 'Named Company'), ('numbered', 'Numbered Company')], default='named', max_length=20)),
                ('company_name_1', models.CharField(blank=True, max_length=255)),
                ('company_name_2', models.CharField(blank=True, max_length=255)),
                ('company_name_3', models.CharField(blank=True, max_length=255)),
                ('french_name_1', models.CharField(blank=True, max_length=255)),
                ('french_name_2', models.CharField(blank=True, max_length=255)),
                ('french_name_3', models.CharField(blank=True, max_length=255)),
                ('jurisdiction', models.CharField(blank=True, max_length=50)),
                ('business_activity', models.CharField(blank=True, max_length=255)),
                ('registered_address', models.TextField(blank=True)),
                ('directors', models.TextField(blank=True)),
                ('shareholders', models.TextField(blank=True)),
                ('notes', models.TextField(blank=True)),
                ('engagement_signed', models.BooleanField(default=False)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(default='new', max_length=30)),
            ],
            options={'ordering': ['-submitted_at']},
        ),
    ]
