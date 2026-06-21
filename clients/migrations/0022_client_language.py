from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0021_onboardingdocument_review_note_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='language',
            field=models.CharField(
                max_length=10,
                choices=[('english', 'English'), ('french', 'French')],
                default='english',
            ),
        ),
    ]
