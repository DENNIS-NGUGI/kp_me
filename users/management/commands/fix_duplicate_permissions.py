# users/management/commands/fix_duplicate_permissions.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from users.models import Role

class Command(BaseCommand):
    help = 'Fix duplicate permissions in the database'

    def handle(self, *args, **options):
        self.stdout.write('Checking for duplicate permissions...')
        
        # Get all permissions grouped by codename
        all_perms = Permission.objects.all()
        perm_groups = {}
        
        for perm in all_perms:
            if perm.codename not in perm_groups:
                perm_groups[perm.codename] = []
            perm_groups[perm.codename].append(perm)
        
        # Find duplicates
        duplicates = {k: v for k, v in perm_groups.items() if len(v) > 1}
        
        if not duplicates:
            self.stdout.write(self.style.SUCCESS('✅ No duplicate permissions found!'))
            return
        
        self.stdout.write(f'⚠️ Found {len(duplicates)} duplicate permission groups:')
        
        # Get the correct content type for Role
        role_content_type = ContentType.objects.get_for_model(Role)
        
        for codename, perms in duplicates.items():
            self.stdout.write(f'\n  📝 {codename}: {len(perms)} copies')
            
            # Find the correct one (with Role content_type)
            correct_perm = None
            for perm in perms:
                if perm.content_type == role_content_type:
                    correct_perm = perm
                    break
            
            # If no permission with Role content_type exists, keep the first one
            if not correct_perm:
                correct_perm = perms[0]
                self.stdout.write(f'    ⚠️ No permission with Role content_type found, keeping first')
            
            # Remove duplicates from all roles
            for perm in perms:
                if perm.id != correct_perm.id:
                    # Remove from roles
                    for role in Role.objects.all():
                        if perm in role.permissions.all():
                            role.permissions.remove(perm)
                            self.stdout.write(f'    🔄 Removed from role: {role.name}')
                    
                    # Delete the duplicate
                    perm.delete()
                    self.stdout.write(f'    🗑️ Deleted duplicate: {perm.id}')
            
            self.stdout.write(self.style.SUCCESS(f'  ✅ Fixed {codename}'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ All duplicates fixed!'))