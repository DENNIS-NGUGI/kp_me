"""
Management command to seed default roles and permissions.
Run: python manage.py seed_roles
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.utils import timezone
from users.models import Role, RoleChangeLog
from users.constants import RoleConstants


class Command(BaseCommand):
    help = 'Seed default roles with permissions and log changes'

    def handle(self, *args, **options):
        self.stdout.write('Seeding default roles...')
        
        # Define default roles with display names, priorities, and styling
        role_configs = {
            'admin': {
                'display_name': 'System Administrator',
                'description': 'Full access to everything',
                'is_system': True,
                'priority': RoleConstants.SYSTEM_ADMIN_PRIORITY,
                'icon': 'bi-shield-lock',
                'color': 'danger',
                'permissions': ['view', 'add', 'change', 'delete'],
                'modules': ['dashboard', 'data_entry', 'indicators', 'reports', 
                           'partners', 'projects', 'users', 'settings', 'audit_log',
                           'field_monitoring', 'fieldvisitreport'],
                'extra_permissions': ['can_approve_field_visit', 'can_export_field_visit']
            },
            'ncpd_me': {
                'display_name': 'NCPD M&E Officer',
                'description': 'Can approve data and manage indicators',
                'is_system': False,
                'priority': RoleConstants.DEFAULT_ADMIN_PRIORITY,
                'icon': 'bi-person-check',
                'color': 'primary',
                'permissions': ['view', 'add', 'change'],
                'modules': ['dashboard', 'data_entry', 'indicators', 'reports', 
                           'partners', 'projects', 'audit_log', 'field_monitoring', 'fieldvisitreport'],
                'extra_permissions': ['can_approve_field_visit', 'can_export_field_visit']
            },
            'county_me': {
                'display_name': 'County M&E Officer',
                'description': 'Can enter and manage county data',
                'is_system': False,
                'priority': RoleConstants.MANAGER_PRIORITY,
                'icon': 'bi-geo-alt',
                'color': 'info',
                'permissions': ['view', 'add', 'change'],
                'modules': ['dashboard', 'data_entry', 'reports', 'field_monitoring', 'fieldvisitreport']
            },
            'partner': {
                'display_name': 'Partner Organization',
                'description': 'Can manage their projects',
                'is_system': False,
                'priority': RoleConstants.USER_PRIORITY,
                'icon': 'bi-handshake',
                'color': 'success',
                'permissions': ['view', 'add', 'change'],
                'modules': ['dashboard', 'partners', 'projects', 'field_monitoring']
            },
            'policy_maker': {
                'display_name': 'Policy Maker',
                'description': 'Read-only access to dashboards and reports',
                'is_system': False,
                'priority': RoleConstants.USER_PRIORITY,
                'icon': 'bi-eye',
                'color': 'secondary',
                'permissions': ['view'],
                'modules': ['dashboard', 'reports', 'field_monitoring']
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
                    'is_system': config['is_system'],
                    'is_active': True,
                    'priority': config['priority'],
                    'icon': config['icon'],
                    'color': config['color'],
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✅ Created role: {role_name}'))
                created_count += 1
                # Log role creation
                RoleChangeLog.objects.create(
                    role=role,
                    change_type='created',
                    new_value={
                        'name': role.name,
                        'display_name': role.display_name,
                        'priority': role.priority,
                    }
                )
            else:
                # Update if changed
                changed = False
                if role.display_name != config['display_name']:
                    role.display_name = config['display_name']
                    changed = True
                if role.description != config['description']:
                    role.description = config['description']
                    changed = True
                if role.priority != config['priority']:
                    role.priority = config['priority']
                    changed = True
                if role.icon != config['icon']:
                    role.icon = config['icon']
                    changed = True
                if role.color != config['color']:
                    role.color = config['color']
                    changed = True
                
                if changed:
                    role.save()
                    self.stdout.write(f'  🔄 Updated role: {role_name}')
                    updated_count += 1
                else:
                    self.stdout.write(f'  ℹ️  Role exists: {role_name}')
            
            # Get permissions for this role
            perm_codenames = []
            for module in config['modules']:
                for action in config['permissions']:
                    perm_codenames.append(f"{action}_{module}")
            perm_codenames.extend(config.get('extra_permissions', []))
            
            # Filter and assign permissions
            perms = all_permissions.filter(codename__in=perm_codenames)
            role.permissions.set(perms)
            
            self.stdout.write(f'    → {perms.count()} permissions assigned')
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✅ Default roles seeded successfully!'))
        self.stdout.write(f'   Created: {created_count} roles')
        self.stdout.write(f'   Updated: {updated_count} roles')
        self.stdout.write(f'   Total roles: {Role.objects.count()}')