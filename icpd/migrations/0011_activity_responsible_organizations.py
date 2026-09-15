from django.db import migrations, models


def migrate_responsible_organizations(apps, schema_editor):
    Activity = apps.get_model('icpd', 'Activity')
    Organization = apps.get_model('users', 'Organization')
    for activity in Activity.objects.exclude(responsibility=''):
        organization = Organization.objects.filter(name__iexact=activity.responsibility.strip()).first()
        if organization:
            activity.responsible_organizations.add(organization)


class Migration(migrations.Migration):
    dependencies = [('icpd', '0010_activity_report_ownership'), ('users', '0013_organization_user_organization')]

    operations = [
        migrations.AddField(
            model_name='activity', name='responsible_organizations',
            field=models.ManyToManyField(blank=True, related_name='responsible_activities', to='users.organization'),
        ),
        migrations.RunPython(migrate_responsible_organizations, migrations.RunPython.noop),
    ]