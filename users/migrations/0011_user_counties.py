from django.db import migrations, models


def copy_legacy_counties(apps, schema_editor):
    User = apps.get_model('users', 'User')
    for user in User.objects.exclude(county__isnull=True).iterator():
        user.counties.add(user.county)


def reverse_copy_legacy_counties(apps, schema_editor):
    User = apps.get_model('users', 'User')
    for user in User.objects.filter(county__isnull=True).iterator():
        county = user.counties.first()
        if county:
            user.county = county
            user.save(update_fields=['county'])


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0010_alter_user_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='counties',
            field=models.ManyToManyField(blank=True, help_text='Counties this user is assigned to', related_name='assigned_users', to='core.county'),
        ),
        migrations.RunPython(copy_legacy_counties, reverse_copy_legacy_counties),
    ]