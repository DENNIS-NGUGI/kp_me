from django.db import migrations, models


def copy_indicator_details(apps, schema_editor):
    ActivityIndicator = apps.get_model('icpd', 'ActivityIndicator')
    for activity_indicator in ActivityIndicator.objects.select_related('indicator'):
        activity_indicator.code = activity_indicator.indicator.code
        activity_indicator.name = activity_indicator.indicator.name
        activity_indicator.save(update_fields=['code', 'name'])


class Migration(migrations.Migration):
    dependencies = [
        ('icpd', '0002_activityyeardata'),
    ]

    operations = [
        migrations.AddField(
            model_name='activityindicator',
            name='code',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='activityindicator',
            name='name',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.RunPython(copy_indicator_details, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='activityindicator',
            name='unique_icpd_indicator_per_activity',
        ),
        migrations.RemoveField(
            model_name='activityindicator',
            name='indicator',
        ),
        migrations.AlterField(
            model_name='activityindicator',
            name='code',
            field=models.CharField(max_length=50),
        ),
        migrations.AlterField(
            model_name='activityindicator',
            name='name',
            field=models.CharField(max_length=500),
        ),
        migrations.AddConstraint(
            model_name='activityindicator',
            constraint=models.UniqueConstraint(
                fields=('activity', 'code'),
                name='unique_icpd_indicator_per_activity',
            ),
        ),
        migrations.AlterModelOptions(
            name='activityindicator',
            options={'ordering': ['activity', 'code']},
        ),
    ]
