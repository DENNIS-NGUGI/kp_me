# users/management/commands/fix_permissions.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from users.models import Role, User

class Command(BaseCommand):
    help = 'Fix permissions for all users and roles'

    def handle(self, *args, **options):
        self.stdout.write('Fixing permissions...')
        
        # 1. Get or create content type
        content_type = ContentType.objects.get_for_model(Role)
        
        # 2. Define all required permissions
        module_actions = [
            ('dashboard', ['view']),
            ('data_entry', ['view', 'add', 'change', 'delete']),
            ('indicators', ['view', 'add', 'change', 'delete']),
            ('reports', ['view', 'add', 'change', 'delete', 'export']),
            ('partners', ['view', 'add', 'change', 'delete']),
            ('projects', ['view', 'add', 'change', 'delete']),
            ('users', ['view', 'add', 'change', 'delete']),
            ('settings', ['view', 'add', 'change', 'delete']),
            ('audit_log', ['view']),
        ]
        
        custom_permissions = [
            'can_manage_users',
            'can_manage_roles',
            'can_manage_system_settings',
            'can_approve_data',
            'can_manage_indicators',
            'can_manage_thematic_areas',
            'view_reports',
            'export_reports',
            'import_data',
            'manage_partners',
            'manage_projects',
            'view_county_data',
            'manage_county_data',
            'view_audit_log',
        ]
        
        # 3. Create module permissions
        self.stdout.write('Creating module permissions...')
        for module, actions in module_actions:
            for action in actions:
                codename = f"{action}_{module}"
                name = f"Can {action} {module}"
                Permission.objects.get_or_create(
                    codename=codename,
                    content_type=content_type,
                    defaults={'name': name}
                )
                self.stdout.write(f'  Created: {codename}')
        
        # 4. Create custom permissions
        self.stdout.write('Creating custom permissions...')
        for codename in custom_permissions:
            name = codename.replace('_', ' ').title()
            Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={'name': name}
            )
            self.stdout.write(f'  Created: {codename}')
        
        # 5. Get all permissions
        all_permissions = Permission.objects.all()
        perm_dict = {p.codename: p for p in all_permissions}
        
        # 6. Define role permissions
        role_permissions = {
            'admin': [
                # Module permissions
                'view_dashboard', 'view_data_entry', 'add_data_entry', 'change_data_entry', 'delete_data_entry',
                'view_indicators', 'add_indicators', 'change_indicators', 'delete_indicators',
                'view_reports', 'add_reports', 'change_reports', 'delete_reports', 'export_reports',
                'view_partners', 'add_partners', 'change_partners', 'delete_partners',
                'view_projects', 'add_projects', 'change_projects', 'delete_projects',
                'view_users', 'add_users', 'change_users', 'delete_users',
                'view_settings', 'add_settings', 'change_settings', 'delete_settings',
                'view_audit_log',
                # Custom permissions
                'can_manage_users', 'can_manage_roles', 'can_manage_system_settings',
                'can_approve_data', 'can_manage_indicators', 'can_manage_thematic_areas',
                'view_reports', 'export_reports', 'import_data',
                'manage_partners', 'manage_projects',
                'view_county_data', 'manage_county_data',
                'view_audit_log',
            ],
            'ncpd_me': [
                'view_dashboard',
                'view_data_entry', 'add_data_entry', 'change_data_entry',
                'view_indicators', 'add_indicators', 'change_indicators',
                'view_reports', 'add_reports', 'change_reports', 'export_reports',
                'view_partners', 'add_partners', 'change_partners',
                'view_projects', 'add_projects', 'change_projects',
                'view_users',
                'can_approve_data', 'can_manage_indicators', 'can_manage_thematic_areas',
                'view_reports', 'export_reports',
                'view_county_data', 'manage_county_data',
            ],
            'county_me': [
                'view_dashboard',
                'view_data_entry', 'add_data_entry', 'change_data_entry',
                'view_indicators',
                'view_reports',
                'view_partners',
                'view_projects',
                'manage_county_data',
                'view_county_data',
            ],
            'partner': [
                'view_dashboard',
                'view_data_entry', 'add_data_entry', 'change_data_entry',
                'view_indicators',
                'view_reports',
                'view_partners', 'add_partners', 'change_partners',
                'view_projects', 'add_projects', 'change_projects',
                'manage_partners',
                'manage_projects',
            ],
            'policy_maker': [
                'view_dashboard',
                'view_reports',
                'view_county_data',
                'view_indicators',
            ],
        }
        
        # 7. Assign permissions to roles
        self.stdout.write('Assigning permissions to roles...')
        for role_name, perm_codenames in role_permissions.items():
            role, created = Role.objects.get_or_create(
                name=role_name,
                defaults={
                    'display_name': role_name.replace('_', ' ').title(),
                    'is_active': True,
                    'is_system': role_name in ['admin', 'ncpd_me'],
                }
            )
            
            # Get permissions
            permissions = []
            for codename in perm_codenames:
                if codename in perm_dict:
                    permissions.append(perm_dict[codename])
                else:
                    self.stdout.write(self.style.WARNING(f'  Permission not found: {codename}'))
            
            # Assign permissions
            role.permissions.set(permissions)
            role.save()
            self.stdout.write(f'  Assigned {len(permissions)} permissions to {role_name}')
        
        self.stdout.write(self.style.SUCCESS('Permissions fixed successfully!'))