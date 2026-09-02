from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from users.models import Role
from django.db import transaction

class Command(BaseCommand):
    help = 'Setup initial permissions for the system'

    def handle(self, *args, **options):
        self.stdout.write('Setting up permissions...')
        
        # Custom permissions
        custom_permissions = [
            # User Management
            ('can_manage_users', 'Can manage users'),
            ('can_manage_roles', 'Can manage roles'),
            ('can_manage_system_settings', 'Can manage system settings'),
            
            # Data Management
            ('can_approve_data', 'Can approve data entries'),
            ('can_manage_indicators', 'Can manage indicators'),
            ('can_manage_thematic_areas', 'Can manage thematic areas'),
            
            # Reports
            ('view_reports', 'Can view reports'),
            ('export_reports', 'Can export reports'),
            ('import_data', 'Can import data'),
            
            # Partners
            ('manage_partners', 'Can manage partner organizations'),
            ('manage_projects', 'Can manage projects'),
            
            # County
            ('view_county_data', 'Can view county data'),
            ('manage_county_data', 'Can manage county data'),
            
            # Audit
            ('view_audit_log', 'Can view audit log'),
        ]
        
        # Get content type for User model
        content_type = ContentType.objects.get_for_model(Role)
        
        with transaction.atomic():
            for codename, name in custom_permissions:
                permission, created = Permission.objects.get_or_create(
                    codename=codename,
                    content_type=content_type,
                    defaults={'name': name}
                )
                if created:
                    self.stdout.write(f'  Created permission: {codename}')
                else:
                    self.stdout.write(f'  Permission exists: {codename}')
        
        self.stdout.write(self.style.SUCCESS('Permissions setup complete!'))