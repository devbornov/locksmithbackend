# Generated by Django 5.1.6 on 2025-02-25 07:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_locksmithservices'),
    ]

    operations = [
        migrations.AddField(
            model_name='locksmithservices',
            name='total_price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
