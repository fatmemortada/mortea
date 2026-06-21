from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0015_client_created_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='CorporateProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jurisdiction', models.CharField(blank=True, choices=[('federal', 'Federal'), ('ontario', 'Ontario'), ('bc', 'British Columbia'), ('quebec', 'Québec')], max_length=20)),
                ('incorporation_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('dissolved', 'Dissolved'), ('in_progress', 'In Progress'), ('inactive', 'Inactive')], default='in_progress', max_length=20)),
                ('business_number', models.CharField(blank=True, max_length=20)),
                ('hst_number', models.CharField(blank=True, max_length=20)),
                ('fiscal_year_end', models.CharField(blank=True, help_text='e.g. December 31', max_length=10)),
                ('registered_address', models.TextField(blank=True)),
                ('annual_return_due', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='corporate_profile', to='clients.client')),
            ],
        ),
        migrations.CreateModel(
            name='Director',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=255)),
                ('address', models.TextField(blank=True)),
                ('appointment_date', models.DateField(blank=True, null=True)),
                ('resignation_date', models.DateField(blank=True, null=True)),
                ('is_officer', models.BooleanField(default=False)),
                ('officer_title', models.CharField(blank=True, help_text='e.g. President, Secretary', max_length=100)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='directors', to='clients.client')),
            ],
        ),
        migrations.CreateModel(
            name='Shareholder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=255)),
                ('address', models.TextField(blank=True)),
                ('share_class', models.CharField(blank=True, default='Common', max_length=50)),
                ('num_shares', models.PositiveIntegerField(default=0)),
                ('acquisition_date', models.DateField(blank=True, null=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shareholders', to='clients.client')),
            ],
        ),
        migrations.CreateModel(
            name='AnnualFiling',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('year', models.PositiveIntegerField()),
                ('due_date', models.DateField()),
                ('filed_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('filed', 'Filed'), ('overdue', 'Overdue')], default='pending', max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='annual_filings', to='clients.client')),
            ],
            options={'ordering': ['-year']},
        ),
    ]
