import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Permission
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from ..models import Role, AuditLog
from ..decorators import permission_required

logger = logging.getLogger(__name__)

def _get_module_permissions(role=None):
    """
    Get all permissions grouped by module
    Handles both custom module permissions and Django auto-generated permissions
    """
    all_perms = Permission.objects.all().order_by('content_type__app_label', 'codename')
    modules = {}
    
    # Define module display names
    module_mapping = {
        # Custom modules (no model)
        'dashboard': 'Dashboard',
        'reports': 'Reports',
        
        # Model modules (Django auto-generated)
        'dataentry': 'Data Entry',
        'indicator': 'Indicators',
        'partner': 'Partners',
        'project': 'Projects',
        'user': 'Users',
        'systemsetting': 'Settings',
        'auditlog': 'Audit Log',
        'county': 'County Data',
        'quarter': 'Quarters',
        'thematicarea': 'Thematic Areas',
        'subcounty': 'Sub County',
        'logentry': 'Log Entry',
        'group': 'Groups',
        'permission': 'Permissions',
        'session': 'Sessions',
        'contenttype': 'Content Types',
        'role': 'Roles',
        'captchastore': 'CAPTCHA',
        'emaildevice': 'Email',
        'notification': 'Notifications',
        'notificationpreference': 'Notification Preferences',
        'projectmilestone': 'Project Milestones',
        'projectreport': 'Project Reports',
    }
    
    # Define valid actions
    valid_actions = {'view', 'add', 'change', 'delete', 'export', 'import', 'approve'}
    
    role_perms = set(role.permissions.values_list('id', flat=True)) if role else set()
    processed_codenames = set()
    
    # Custom permissions (can_* prefix or custom module permissions)
    custom_permissions = [
        # Custom module permissions (no model)
        'view_dashboard', 'add_dashboard', 'change_dashboard', 'delete_dashboard',
        'view_reports', 'add_reports', 'change_reports', 'delete_reports', 'export_reports',
        
        # Custom can_* permissions
        'can_manage_users', 'can_manage_roles', 'can_manage_system_settings',
        'can_approve_data', 'can_manage_indicators', 'can_manage_thematic_areas',
        'can_import_data', 'can_manage_partners', 'can_manage_projects',
        'can_manage_county_data',
    ]
    
    for perm in all_perms:
        codename = perm.codename
        
        if codename in processed_codenames:
            continue
        
        # Check if it's a custom permission
        if codename in custom_permissions:
            if 'custom' not in modules:
                modules['custom'] = {
                    'name': 'Custom Permissions',
                    'permissions': []
                }
            
            modules['custom']['permissions'].append({
                'id': perm.id,
                'codename': codename,
                'name': perm.name,
                'action': 'custom',
                'checked': perm.id in role_perms
            })
            processed_codenames.add(codename)
            continue
        
        # Check if it's a module permission (action_modelname format)
        is_module_perm = False
        action = None
        module_key = None
        
        for valid_action in valid_actions:
            if codename.startswith(f"{valid_action}_"):
                parts = codename.split('_', 1)
                if len(parts) == 2:
                    action = parts[0]
                    module_key = parts[1].lower()
                    is_module_perm = True
                    break
        
        if is_module_perm and module_key:
            display_name = module_mapping.get(module_key, module_key.replace('_', ' ').title())
            
            if module_key not in modules:
                modules[module_key] = {
                    'name': display_name,
                    'permissions': []
                }
            
            # Check if this permission already exists in this module
            exists = any(p['codename'] == codename for p in modules[module_key]['permissions'])
            if not exists:
                modules[module_key]['permissions'].append({
                    'id': perm.id,
                    'codename': codename,
                    'name': perm.name,
                    'action': action,
                    'checked': perm.id in role_perms
                })
                processed_codenames.add(codename)
    
    # Sort permissions within each module by action
    action_order = {'view': 0, 'add': 1, 'change': 2, 'delete': 3, 'export': 4, 'import': 5, 'approve': 6, 'custom': 7}
    
    for module_key in modules:
        modules[module_key]['permissions'].sort(
            key=lambda x: (action_order.get(x.get('action', 'custom'), 99), x['codename'])
        )
    
    # Sort modules by name (put custom at the end)
    sorted_modules = {}
    for module_key in sorted(modules.keys()):
        if module_key != 'custom':
            sorted_modules[module_key] = modules[module_key]
    
    if 'custom' in modules:
        sorted_modules['custom'] = modules['custom']
    
    return sorted_modules

@login_required
@permission_required('can_manage_roles')
def role_list(request):
    """List all roles with their permissions - uses database permission"""
    roles = Role.objects.prefetch_related('permissions', 'users').all().order_by('name')
    
    # Define module mappings
    module_mapping = {
        'dashboard': 'Dashboard',
        'data_entry': 'Data Entry',
        'indicators': 'Indicators',
        'reports': 'Reports',
        'partners': 'Partners',
        'projects': 'Projects',
        'users': 'Users',
        'settings': 'Settings',
        'audit_log': 'Audit Log',
        'core': 'Core',
    }
    
    # Build role data with permissions organized by module
    role_data = []
    for role in roles:
        # Get all permissions
        all_perms = role.permissions.all()
        
        # Organize by module
        modules = {}
        custom_perms = []
        
        for perm in all_perms:
            codename = perm.codename
            
            # Check if it's a module permission (action_module format)
            if '_' in codename and not codename.startswith('can_'):
                parts = codename.split('_', 1)
                if len(parts) == 2:
                    action, module = parts
                    if module and action in ['view', 'add', 'change', 'delete', 'export', 'import', 'approve']:
                        if module not in modules:
                            modules[module] = {
                                'display': module_mapping.get(module, module.replace('_', ' ').title()),
                                'actions': []
                            }
                        modules[module]['actions'].append(action)
                        continue
            
            # Custom permission
            custom_perms.append(codename)
        
        # Sort actions
        for module in modules:
            modules[module]['actions'].sort()
        
        role_data.append({
            'id': role.id,
            'name': role.name,
            'display_name': role.display_name,
            'description': role.description,
            'icon': role.icon,
            'color': role.color,
            'is_system': role.is_system,
            'is_active': role.is_active,
            'priority': role.priority,
            'created_at': role.created_at,
            'perm_codenames': [p.codename for p in all_perms],
            'modules': modules,  # New: organized by module
            'custom_perms': custom_perms,  # New: custom permissions
            'user_count': role.users.count(),
        })
    
    context = {
        'roles': role_data,
    }
    return render(request, 'users/roles.html', context)

@login_required
@permission_required('can_manage_roles')
def role_add(request):
    """
    Add a new role - FULLY DATABASE DRIVEN
    """
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        display_name = request.POST.get('display_name', '').strip()
        description = request.POST.get('description', '').strip()
        icon = request.POST.get('icon', 'bi-person')
        color = request.POST.get('color', 'secondary')
        priority = request.POST.get('priority', 0)
        
        # Validate
        if not name:
            messages.error(request, 'Role name is required.')
            return render(request, 'users/role_form.html')
        
        if Role.objects.filter(name=name).exists():
            messages.error(request, f'Role "{name}" already exists.')
            return render(request, 'users/role_form.html')
        
        if not display_name:
            display_name = name.replace('_', ' ').title()
        
        try:
            # Create role
            role = Role.objects.create(
                name=name,
                display_name=display_name,
                description=description,
                icon=icon,
                color=color,
                priority=int(priority),
                is_system=False,
                is_active=True
            )
            
            # Assign permissions if any selected
            permission_ids = request.POST.getlist('permissions')
            if permission_ids:
                permissions = Permission.objects.filter(id__in=permission_ids)
                role.permissions.set(permissions)
            
            # Log the creation
            AuditLog.log(
                user=request.user,
                action=AuditLog.Action.CREATE,
                request=request,
                model_instance=role
            )
            
            messages.success(request, f'Role "{role.get_display_name()}" created successfully!')
            return redirect('users:role_list')
            
        except Exception as e:
            logger.error(f"Role creation error: {e}")
            messages.error(request, 'An error occurred while creating the role. Please try again.')
            return render(request, 'users/role_form.html')
    
    # GET - display form
    modules = _get_module_permissions()
    
    colors = [
        ('primary', 'Primary (Blue)'),
        ('success', 'Success (Green)'),
        ('danger', 'Danger (Red)'),
        ('warning', 'Warning (Yellow)'),
        ('info', 'Info (Cyan)'),
        ('secondary', 'Secondary (Gray)'),
        ('dark', 'Dark'),
    ]
    
    icons = [
        'bi-person', 'bi-people', 'bi-person-badge', 
        'bi-shield-lock', 'bi-building', 'bi-geo-alt',
        'bi-star', 'bi-trophy', 'bi-award', 'bi-flag',
        'bi-briefcase', 'bi-folder', 'bi-file-earmark',
        'bi-house', 'bi-globe', 'bi-gear', 'bi-tools'
    ]
    
    context = {
        'modules': modules,
        'colors': colors,
        'icons': icons,
        'is_edit': False,
    }
    return render(request, 'users/role_form.html', context)

@login_required
@permission_required('can_manage_roles')
def role_edit(request, pk):
    """
    Edit a role - FULLY DATABASE DRIVEN
    """
    role = get_object_or_404(Role, pk=pk)
    
    if role.is_system and not request.user.is_superuser:
        messages.warning(request, 'System roles can only be modified by superusers.')
        return redirect('users:role_list')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        display_name = request.POST.get('display_name', '').strip()
        description = request.POST.get('description', '').strip()
        icon = request.POST.get('icon', role.icon)
        color = request.POST.get('color', role.color)
        priority = request.POST.get('priority', role.priority)
        is_active = request.POST.get('is_active') == 'on'
        
        # Validate
        if not name:
            messages.error(request, 'Role name is required.')
            return render(request, 'users/role_form.html', {'role': role})
        
        if Role.objects.filter(name=name).exclude(pk=pk).exists():
            messages.error(request, f'Role "{name}" already exists.')
            return render(request, 'users/role_form.html', {'role': role})
        
        try:
            changes = {}
            
            if role.name != name:
                changes['name'] = {'old': role.name, 'new': name}
                role.name = name
            
            if role.display_name != display_name:
                changes['display_name'] = {'old': role.display_name, 'new': display_name}
                role.display_name = display_name or name.replace('_', ' ').title()
            
            if role.description != description:
                changes['description'] = {'old': role.description, 'new': description}
                role.description = description
            
            if role.icon != icon:
                changes['icon'] = {'old': role.icon, 'new': icon}
                role.icon = icon
            
            if role.color != color:
                changes['color'] = {'old': role.color, 'new': color}
                role.color = color
            
            if role.priority != int(priority):
                changes['priority'] = {'old': role.priority, 'new': int(priority)}
                role.priority = int(priority)
            
            if role.is_active != is_active and not role.is_system:
                changes['is_active'] = {'old': role.is_active, 'new': is_active}
                role.is_active = is_active
            
            # Update permissions
            permission_ids = request.POST.getlist('permissions')
            old_perms = set(role.permissions.values_list('id', flat=True))
            new_perms = set(map(int, permission_ids)) if permission_ids else set()
            
            if old_perms != new_perms:
                changes['permissions'] = {
                    'old': list(old_perms),
                    'new': list(new_perms)
                }
                
                if permission_ids:
                    permissions = Permission.objects.filter(id__in=permission_ids)
                    role.permissions.set(permissions)
                else:
                    role.permissions.clear()
            
            role.save()
            
            # Log the changes
            if changes:
                AuditLog.log(
                    user=request.user,
                    action=AuditLog.Action.UPDATE,
                    request=request,
                    model_instance=role,
                    changes=changes
                )
                messages.success(request, f'Role "{role.get_display_name()}" updated successfully!')
            else:
                messages.info(request, 'No changes were made.')
            
            return redirect('users:role_list')
            
        except Exception as e:
            logger.error(f"Role update error: {e}")
            messages.error(request, 'An error occurred while updating the role. Please try again.')
            return render(request, 'users/role_form.html', {'role': role})
    
    # GET - display form
    modules = _get_module_permissions(role)
    
    colors = [
        ('primary', 'Primary (Blue)'),
        ('success', 'Success (Green)'),
        ('danger', 'Danger (Red)'),
        ('warning', 'Warning (Yellow)'),
        ('info', 'Info (Cyan)'),
        ('secondary', 'Secondary (Gray)'),
        ('dark', 'Dark'),
    ]
    
    icons = [
        'bi-person', 'bi-people', 'bi-person-badge', 
        'bi-shield-lock', 'bi-building', 'bi-geo-alt',
        'bi-star', 'bi-trophy', 'bi-award', 'bi-flag',
        'bi-briefcase', 'bi-folder', 'bi-file-earmark',
        'bi-house', 'bi-globe', 'bi-gear', 'bi-tools'
    ]
    
    context = {
        'role': role,
        'modules': modules,
        'colors': colors,
        'icons': icons,
        'is_edit': True,
    }
    return render(request, 'users/role_form.html', context)

@login_required
@permission_required('can_manage_roles')
def role_delete(request, pk):
    """
    Delete a role - uses database permission
    """
    role = get_object_or_404(Role, pk=pk)
    
    if role.is_system:
        messages.warning(request, 'System roles cannot be deleted.')
        return redirect('users:role_list')
    
    # Check if role has users
    user_count = role.users.count()
    if user_count > 0:
        messages.warning(
            request, 
            f'Cannot delete role "{role.get_display_name()}" as it has {user_count} users assigned. '
            'Please reassign users to another role first.'
        )
        return redirect('users:role_list')
    
    if request.method == 'POST':
        role_name = role.get_display_name()
        
        # Log the deletion
        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.DELETE,
            request=request,
            model_instance=role
        )
        
        role.delete()
        messages.success(request, f'Role "{role_name}" deleted successfully!')
        return redirect('users:role_list')
    
    return render(request, 'users/role_delete.html', {'role': role})

@login_required
@permission_required('can_manage_roles')
def role_update_permissions(request, pk):
    """
    Update permissions for a role - uses database permission
    """
    role = get_object_or_404(Role, pk=pk)
    
    if role.is_system:
        messages.warning(request, 'System roles cannot be modified.')
        return redirect('users:role_list')
    
    if request.method == 'POST':
        permission_codenames = request.POST.getlist('permissions')
        
        if permission_codenames:
            permissions = Permission.objects.filter(codename__in=permission_codenames)
            old_perms = set(role.permissions.values_list('id', flat=True))
            new_perms = set(permissions.values_list('id', flat=True))
            
            role.permissions.set(permissions)
            
            # Log the changes
            AuditLog.log(
                user=request.user,
                action=AuditLog.Action.UPDATE,
                request=request,
                model_instance=role,
                changes={
                    'permissions': {
                        'old': list(old_perms),
                        'new': list(new_perms)
                    }
                }
            )
            
            messages.success(request, f'Permissions for "{role.get_display_name()}" updated successfully!')
        else:
            role.permissions.clear()
            messages.info(request, f'All permissions removed from "{role.get_display_name()}".')
        
        return redirect('users:role_list')
    
    return redirect('users:role_list')

@login_required
@permission_required('can_manage_roles')
def role_clone(request, pk):
    """
    Clone an existing role - uses database permission
    """
    source_role = get_object_or_404(Role, pk=pk)
    
    if request.method == 'POST':
        new_name = request.POST.get('name', '').strip()
        new_display_name = request.POST.get('display_name', '').strip()
        
        if not new_name:
            messages.error(request, 'Role name is required.')
            return render(request, 'users/role_clone.html', {'source_role': source_role})
        
        if Role.objects.filter(name=new_name).exists():
            messages.error(request, f'Role "{new_name}" already exists.')
            return render(request, 'users/role_clone.html', {'source_role': source_role})
        
        # Create new role with copied permissions
        new_role = Role.objects.create(
            name=new_name,
            display_name=new_display_name or new_name.replace('_', ' ').title(),
            description=f"Cloned from {source_role.get_display_name()}",
            icon=source_role.icon,
            color=source_role.color,
            priority=source_role.priority,
            is_system=False,
            is_active=True
        )
        
        # Copy permissions
        new_role.permissions.set(source_role.permissions.all())
        
        # Log the creation
        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.CREATE,
            request=request,
            model_instance=new_role,
            changes={'cloned_from': source_role.get_display_name()}
        )
        
        messages.success(request, f'Role "{new_role.get_display_name()}" cloned successfully!')
        return redirect('users:role_list')
    
    return render(request, 'users/role_clone.html', {'source_role': source_role})