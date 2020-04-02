# Generated by Django 3.0.4 on 2020-04-02 17:35

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Contribution',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=2000)),
                ('points', models.IntegerField(default=1)),
                ('publication_time', models.DateTimeField(verbose_name='publication date')),
                ('url', models.CharField(blank=True, max_length=500, null=True)),
                ('text', models.CharField(blank=True, max_length=2000, null=True)),
                ('comments', models.IntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('username', models.CharField(max_length=15, primary_key=True, serialize=False)),
                ('password', models.CharField(max_length=72)),
                ('hidden', models.ManyToManyField(blank=True, related_name='hidden_contributions', to='empo_news.Contribution')),
                ('upvoted', models.ManyToManyField(blank=True, related_name='upvoted_contributions', to='empo_news.Contribution')),
            ],
        ),
        migrations.AddField(
            model_name='contribution',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='empo_news.User'),
        ),
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('upvotes', models.IntegerField(default=1)),
                ('publication_date', models.DateTimeField(verbose_name='publication date')),
                ('text', models.CharField(max_length=2000)),
                ('contribution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='empo_news.Contribution')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='empo_news.User')),
            ],
        ),
    ]
