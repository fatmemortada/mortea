from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0026_alter_subscription_active_default'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformAgreement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('signed_name', models.CharField(max_length=255)),
                ('signed_email', models.EmailField()),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('agreement_version', models.CharField(default='v1', max_length=10)),
                ('signed_at', models.DateTimeField(auto_now_add=True)),
                ('firm', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='platform_agreements', to='clients.firm')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='platform_agreement', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
