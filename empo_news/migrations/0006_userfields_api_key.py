# Generated by Django 3.0.4 on 2020-04-30 18:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empo_news', '0005_auto_20200430_2031'),
    ]

    operations = [
        migrations.AddField(
            model_name='userfields',
            name='api_key',
            field=models.CharField(default='', max_length=20),
        ),
    ]
