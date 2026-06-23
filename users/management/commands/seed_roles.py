"""
Management command to seed default roles and permissions.
Run: python manage.py seed_roles
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from users.models import Role


class Command(BaseCommand):
    help = 'Seed default roles with permissions'

    def handle(self, *args, **options):
        self.stdout.write('Seeding default roles...')
        
        # Define default roles with display names
        role_configs = {
            'admin': {
                'display_name': 'System Administrator',
                'description': 'Full access to everything',
                'is_system': True,
                'permissions': ['view', 'add', 'change', 'delete'],
                'modules': ['dashboard', 'data_entry', 'indicators', 'reports', 
                           'partners', 'projects', 'users', 'settings', 'audit_log']
            },
            'ncpd_me': {
                'display_name': 'NCPD M&E Officer',
                'description': 'Can approve data and manage indicators',
                'is_system': True,
                'permissions': ['view', 'add', 'change'],
                'modules': ['dashboard', 'data_entry', 'indicators', 'reports', 
                           'partners', 'projects', 'audit_log']
            },
            'county_me': {
                'display_name': 'County M&E Officer',
                'description': 'Can enter and manage county data',
                'is_system': True,
                'permissions': ['view', 'add', 'change'],
                'modules': ['dashboard', 'data_entry', 'reports']
            },
            'partner': {
                'display_name': 'Partner Organization',
                'description': 'Can manage their projects',
                'is_system': True,
                'permissions': ['view', 'add', 'change'],
                'modules': ['dashboard', 'partners', 'projects']
            },
            'policy_maker': {
                'display_name': 'Policy Maker',
                'description': 'Read-only access to dashboards and reports',
                'is_system': True,
                'permissions': ['view'],
                'modules': ['dashboard', 'reports']
            },
        }
        
        all_permissions = Permission.objects.all()
        
        if not all_permissions.exists():
            self.stdout.write(self.style.WARNING('No permissions found. Run migrations first.'))
            return
        
        created_count = 0
        updated_count = 0
        
        for role_name, config in role_configs.items():
            # Get or create role
            role, created = Role.objects.get_or_create(
                name=role_name,
                defaults={
                    'display_name': config['display_name'],
                    'description': config['description'],
                    'is_system': True,
                    'is_active': True
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✅ Created role: {role_name}'))
                created_count += 1
            else:
                # Update display name if changed
                if role.display_name != config['display_name']:
                    role.display_name = config['display_name']
                    role.description = config['description']
                    role.save()
                    self.stdout.write(f'  🔄 Updated role: {role_name}')
                    updated_count += 1
                else:
                    self.stdout.write(f'  🔄 Updating role: {role_name}')
                    updated_count += 1
            
            # Get permissions for this role
            perm_codenames = []
            for module in config['modules']:
                for action in config['permissions']:
                    perm_codenames.append(f"{action}_{module}")
            
            # Filter and assign permissions
            perms = all_permissions.filter(codename__in=perm_codenames)
            role.permissions.set(perms)
            
            self.stdout.write(f'    → {perms.count()} permissions assigned')
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✅ Default roles seeded successfully!'))
        self.stdout.write(f'   Created: {created_count} roles')
        self.stdout.write(f'   Updated: {updated_count} roles')
        self.stdout.write(f'   Total roles: {Role.objects.count()}')