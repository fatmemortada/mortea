from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0023_bookkeeping_expanded'),
    ]

    operations = [
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('invoice_number', models.CharField(max_length=50, blank=True)),
                ('description', models.TextField()),
                ('service_type', models.CharField(
                    max_length=30,
                    choices=[
                        ('bookkeeping', 'Bookkeeping'),
                        ('tax_return', 'Tax Return'),
                        ('incorporation', 'Incorporation'),
                        ('consultation', 'Consultation'),
                        ('hst_filing', 'HST/GST Filing'),
                        ('payroll', 'Payroll'),
                        ('other', 'Other'),
                    ],
                    default='bookkeeping',
                )),
                ('amount', models.DecimalField(max_digits=10, decimal_places=2)),
                ('status', models.CharField(
                    max_length=20,
                    choices=[
                        ('draft', 'Draft'),
                        ('sent', 'Sent'),
                        ('paid', 'Paid'),
                        ('overdue', 'Overdue'),
                    ],
                    default='draft',
                )),
                ('invoice_date', models.DateField()),
                ('due_date', models.DateField(null=True, blank=True)),
                ('paid_date', models.DateField(null=True, blank=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('client', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='invoices',
                    to='clients.client',
                )),
            ],
            options={
                'ordering': ['-invoice_date'],
            },
        ),
    ]
