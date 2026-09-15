from django.db import migrations, models
import django.db.models.deletion


def migrate_organizations(apps, schema_editor):
    Organization = apps.get_model('users', 'Organization')
    User = apps.get_model('users', 'User')
    for user in User.objects.exclude(legacy_organization=''):
        organization, _ = Organization.objects.get_or_create(name=user.legacy_organization.strip())
        user.organization = organization
        user.save(update_fields=['organization'])


class Migration(migrations.Migration):
    dependencies = [('users', '0012_user_force_password_change')]

    operations = [
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, unique=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.RenameField(model_name='user', old_name='organization', new_name='legacy_organization'),
        migrations.AddField(
            model_name='user', name='organization',
            field=models.ForeignKey(blank=True, help_text='Organization the user belongs to', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='users', to='users.organization'),
        ),
        migrations.RunPython(migrate_organizations, migrations.RunPython.noop),
        migrations.RemoveField(model_name='user', name='legacy_organization'),
    ]