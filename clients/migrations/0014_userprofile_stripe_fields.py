from django.db import migrations, models
 
 
class Migration(migrations.Migration):
 
    dependencies = [
        ('clients', '0012_client_client_token_client_user_firm_code_and_more'),
    ]
 
    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='stripe_customer_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='stripe_subscription_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='subscription_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='billing_cycle',
            field=models.CharField(blank=True, default='monthly', max_length=20),
        ),
    ]
