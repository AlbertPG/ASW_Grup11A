# Generated by Django 3.0.4 on 2020-04-30 18:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empo_news', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='contribution',
            name='num_likes',
            field=models.IntegerField(default=0),
        ),
    ]
