# Generated by Django 5.1.6 on 2025-02-26 07:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_alter_customerservicerequest_service_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='locksmithservices',
            name='service_type',
            field=models.CharField(choices=[('smart_lock', 'Smart Lock'), ('emergency', 'Emergency'), ('automotive', 'Automotive'), ('commercial', 'Commercial'), ('residential', 'Residential')], default='residential', max_length=20),
        ),
    ]
