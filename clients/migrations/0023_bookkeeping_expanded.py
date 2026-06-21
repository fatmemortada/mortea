from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0022_client_language'),
    ]

    operations = [
        # Expand BookkeepingTask
        migrations.AddField(
            model_name='bookkeepingtask',
            name='hst_status',
            field=models.CharField(
                max_length=20,
                choices=[('na', 'N/A'), ('pending', 'Pending'), ('filed', 'Filed')],
                default='na',
            ),
        ),
        migrations.AddField(
            model_name='bookkeepingtask',
            name='billed',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='bookkeepingtask',
            name='status',
            field=models.CharField(
                max_length=30,
                choices=[
                    ('not_started', 'Not Started'),
                    ('documents_requested', 'Documents Requested'),
                    ('documents_received', 'Documents Received'),
                    ('in_progress', 'In Progress'),
                    ('completed', 'Completed'),
                ],
                default='not_started',
            ),
        ),
        # New BookkeepingDocument model
        migrations.CreateModel(
            name='BookkeepingDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(
                    max_length=30,
                    choices=[
                        ('bank_statement', 'Bank Statement'),
                        ('credit_card', 'Credit Card Statement'),
                        ('receipts', 'Receipts'),
                        ('invoices', 'Invoices'),
                        ('payroll', 'Payroll'),
                        ('other', 'Other'),
                    ],
                )),
                ('document_name', models.CharField(max_length=255)),
                ('file', models.FileField(upload_to='documents/bookkeeping/')),
                ('uploaded_by', models.CharField(
                    max_length=20,
                    choices=[('client', 'Client'), ('accountant', 'Accountant')],
                    default='accountant',
                )),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('task', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='documents',
                    to='clients.bookkeepingtask',
                )),
            ],
        ),
    ]
