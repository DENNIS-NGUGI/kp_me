import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.http import require_http_methods

from ..models import User, Role, AuditLog
from ..decorators import permission_required
from ..validators import validate_phone_number
from core.models import County

logger = logging.getLogger(__name__)

@login_required
@permission_required('can_manage_users')
def user_management(request):
    """
    Manage users - uses database permission
    Lists all users with filtering and search capabilities
    """
    users = User.objects.select_related('role', 'county').all().order_by('-date_joined')
    
    # Apply filters
    role_filter = request.GET.get('role')
    county_filter = request.GET.get('county')
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status')  # active, inactive, all
    
    if role_filter:
        users = users.filter(role_id=role_filter)
    if county_filter:
        users = users.filter(county_id=county_filter)
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(organization__icontains=search_query)
        )
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    
    # Get statistics
    total_users = users.count()
    active_users = users.filter(is_active=True).count()
    verified_users = users.filter(is_verified=True).count()
    
    roles = Role.objects.filter(is_active=True)
    counties = County.objects.filter(is_active=True)
    
    context = {
        'users': users,
        'roles': roles,
        'counties': counties,
        'selected_role': role_filter,
        'selected_county': county_filter,
        'search_query': search_query,
        'status_filter': status_filter,
        'total_users': total_users,
        'active_users': active_users,
        'verified_users': verified_users,
    }
    return render(request, 'users/user_management.html', context)

@login_required
@permission_required('can_manage_users')
def user_edit(request, pk):
    """
    Edit user details - uses database permission
    Allows admins to modify user accounts
    """
    user_obj = get_object_or_404(
        User.objects.select_related('role', 'county'), 
        pk=pk
    )
    
    # Prevent editing superusers by non-superusers
    if user_obj.is_superuser and not request.user.is_superuser:
        messages.warning(request, 'You cannot edit superuser accounts.')
        return redirect('users:user_management')
    
    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone_number = request.POST.get('phone_number', '').strip()
        organization = request.POST.get('organization', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        is_verified = request.POST.get('is_verified') == 'on'
        role_id = request.POST.get('role')
        county_id = request.POST.get('county')
        
        errors = []
        changes = {}
        
        # Validate email uniqueness
        if email:
            if User.objects.filter(email=email).exclude(pk=user_obj.pk).exists():
                errors.append('Email already in use by another account.')
        else:
            errors.append('Email is required.')
        
        # Validate phone number
        if phone_number and not validate_phone_number(phone_number):
            errors.append('Please enter a valid phone number (e.g., +254712345678).')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'users/user_edit.html', {'edit_user': user_obj})
        
        # Track changes
        if user_obj.first_name != first_name:
            changes['first_name'] = {'old': user_obj.first_name, 'new': first_name}
            user_obj.first_name = first_name
        
        if user_obj.last_name != last_name:
            changes['last_name'] = {'old': user_obj.last_name, 'new': last_name}
            user_obj.last_name = last_name
        
        if user_obj.email != email:
            changes['email'] = {'old': user_obj.email, 'new': email}
            user_obj.email = email
        
        if user_obj.phone_number != phone_number:
            changes['phone_number'] = {'old': user_obj.phone_number, 'new': phone_number}
            user_obj.phone_number = phone_number
        
        if user_obj.organization != organization:
            changes['organization'] = {'old': user_obj.organization, 'new': organization}
            user_obj.organization = organization
        
        if user_obj.is_active != is_active:
            changes['is_active'] = {'old': user_obj.is_active, 'new': is_active}
            user_obj.is_active = is_active
        
        if user_obj.is_verified != is_verified:
            changes['is_verified'] = {'old': user_obj.is_verified, 'new': is_verified}
            user_obj.is_verified = is_verified
        
        # Update role
        new_role = None
        if role_id:
            try:
                new_role = Role.objects.get(id=role_id, is_active=True)
                if user_obj.role_id != new_role.id:
                    changes['role'] = {
                        'old': user_obj.role.get_display_name() if user_obj.role else None,
                        'new': new_role.get_display_name()
                    }
                    user_obj.role = new_role
            except Role.DoesNotExist:
                pass
        else:
            if user_obj.role:
                changes['role'] = {'old': user_obj.role.get_display_name(), 'new': None}
                user_obj.role = None
        
        # Update county
        new_county = None
        if county_id:
            try:
                new_county = County.objects.get(id=county_id, is_active=True)
                if user_obj.county_id != new_county.id:
                    changes['county'] = {
                        'old': user_obj.county.name if user_obj.county else None,
                        'new': new_county.name
                    }
                    user_obj.county = new_county
            except County.DoesNotExist:
                pass
        else:
            if user_obj.county:
                changes['county'] = {'old': user_obj.county.name, 'new': None}
                user_obj.county = None
        
        # Save user
        user_obj.save()
        
        # Log the changes
        if changes:
            AuditLog.log(
                user=request.user,
                action=AuditLog.Action.UPDATE,
                request=request,
                model_instance=user_obj,
                changes=changes
            )
            messages.success(
                request, 
                f'User "{user_obj.get_full_name() or user_obj.username}" updated successfully!'
            )
        else:
            messages.info(request, 'No changes were made.')
        
        return redirect('users:user_management')
    
    counties = County.objects.filter(is_active=True)
    roles = Role.objects.filter(is_active=True)
    
    context = {
        'edit_user': user_obj,
        'counties': counties,
        'roles': roles,
    }
    return render(request, 'users/user_edit.html', context)

@login_required
@permission_required('can_manage_users')
@require_http_methods(["POST"])
def user_toggle_status(request, pk):
    """
    Toggle user active status - uses database permission
    """
    user_obj = get_object_or_404(User, pk=pk)
    
    # Prevent toggling superuser status for non-superusers
    if user_obj.is_superuser and not request.user.is_superuser:
        messages.warning(request, 'Cannot change superuser status.')
        return redirect('users:user_management')
    
    # Prevent toggling own status
    if user_obj.pk == request.user.pk:
        messages.warning(request, 'You cannot deactivate your own account.')
        return redirect('users:user_management')
    
    old_status = user_obj.is_active
    user_obj.is_active = not user_obj.is_active
    user_obj.save()
    
    # Log the change
    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.UPDATE,
        request=request,
        model_instance=user_obj,
        changes={
            'is_active': {
                'old': old_status,
                'new': user_obj.is_active
            }
        }
    )
    
    status = 'activated' if user_obj.is_active else 'deactivated'
    messages.success(
        request, 
        f'User "{user_obj.get_full_name() or user_obj.username}" {status} successfully!'
    )
    return redirect('users:user_management')

@login_required
@permission_required('can_manage_users')
def user_delete(request, pk):
    """
    Delete a user - uses database permission
    """
    user_obj = get_object_or_404(User, pk=pk)
    
    # Prevent deleting superusers
    if user_obj.is_superuser:
        messages.warning(request, 'Cannot delete superuser.')
        return redirect('users:user_management')
    
    # Prevent deleting self
    if user_obj.pk == request.user.pk:
        messages.warning(request, 'You cannot delete your own account.')
        return redirect('users:user_management')
    
    if request.method == 'POST':
        username = user_obj.get_full_name() or user_obj.username
        
        # Log the deletion
        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.DELETE,
            request=request,
            model_instance=user_obj
        )
        
        # Use hard_delete for permanent deletion
        user_obj.hard_delete()
        messages.success(request, f'User "{username}" deleted successfully!')
        return redirect('users:user_management')
    
    return render(request, 'users/user_delete.html', {'user': user_obj})

@login_required
@permission_required('can_manage_users')
def user_bulk_action(request):
    """
    Perform bulk actions on users
    """
    if request.method == 'POST':
        user_ids = request.POST.getlist('user_ids')
        action = request.POST.get('bulk_action')
        
        if not user_ids:
            messages.warning(request, 'No users selected.')
            return redirect('users:user_management')
        
        if action == 'activate':
            count = User.objects.filter(id__in=user_ids).update(is_active=True)
            messages.success(request, f'{count} users activated successfully!')
        elif action == 'deactivate':
            # Prevent deactivating self
            if str(request.user.id) in user_ids:
                messages.warning(request, 'You cannot deactivate your own account.')
                user_ids.remove(str(request.user.id))
            count = User.objects.filter(id__in=user_ids).update(is_active=False)
            messages.success(request, f'{count} users deactivated successfully!')
        elif action == 'delete':
            # Prevent deleting self and superusers
            users = User.objects.filter(id__in=user_ids)
            if request.user.id in user_ids:
                messages.warning(request, 'You cannot delete your own account.')
                users = users.exclude(id=request.user.id)
            users = users.exclude(is_superuser=True)
            count = users.count()
            for user in users:
                user.hard_delete()
            messages.success(request, f'{count} users deleted successfully!')
        else:
            messages.warning(request, 'Invalid action selected.')
        
        return redirect('users:user_management')
    
    return redirect('users:user_management')