import logging
import secrets
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.views.decorators.http import require_http_methods

from ..models import User, Role, AuditLog, Organization
from ..decorators import permission_required
from ..validators import validate_phone_number
from ..utils import send_registration_email
from core.models import County

logger = logging.getLogger(__name__)


@login_required
@permission_required('can_manage_users')
def organization_management(request):
    if request.method == 'POST':
        organization_id = request.POST.get('organization_id')
        name = request.POST.get('name', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        if not name:
            messages.error(request, 'Organization name is required.')
        elif Organization.objects.exclude(pk=organization_id).filter(name__iexact=name).exists():
            messages.error(request, 'An organization with this name already exists.')
        else:
            organization = get_object_or_404(Organization, pk=organization_id) if organization_id else Organization()
            organization.name = name
            organization.is_active = is_active
            organization.save()
            messages.success(request, f'Organization "{organization.name}" saved successfully.')
        return redirect('users:organization_management')

    return render(request, 'users/organization_management.html', {
        'organizations': Organization.objects.all(),
    })


@login_required
@permission_required('can_manage_users')
def user_management(request):
    """
    Manage users - uses database permission
    Lists all users with filtering and search capabilities
    """
    users = User.objects.select_related('role').prefetch_related('counties').all().order_by('-date_joined')
    
    # Apply filters
    role_filter = request.GET.get('role')
    county_filter = request.GET.get('county')
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status')  # active, inactive, all
    
    if role_filter:
        users = users.filter(role_id=role_filter)
    if county_filter:
        users = users.filter(counties__id=county_filter)
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(organization__name__icontains=search_query)
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
    organizations = Organization.objects.filter(is_active=True)
    
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
def user_add(request):
    """Create a verified user and send a temporary password by email."""
    roles = Role.objects.filter(is_active=True)
    counties = County.objects.filter(is_active=True)
    organizations = Organization.objects.filter(is_active=True)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip().lower()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        organization = organizations.filter(pk=request.POST.get('organization')).first() if request.POST.get('organization') else None
        role_id = request.POST.get('role')
        county_ids = request.POST.getlist('counties')
        errors = []

        if not username:
            errors.append('Username is required.')
        elif len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        elif User.objects.filter(username__iexact=username).exists():
            errors.append('Username already exists.')
        elif not username.replace('_', '').replace('-', '').isalnum():
            errors.append('Username can only contain letters, numbers, underscores, and hyphens.')

        if not email:
            errors.append('Email is required.')
        elif User.objects.filter(email=email).exists():
            errors.append('Email already in use by another account.')

        if phone_number and not validate_phone_number(phone_number):
            errors.append('Please enter a valid phone number (e.g., +254712345678).')

        role = None
        if role_id:
            try:
                role = roles.get(pk=role_id)
            except Role.DoesNotExist:
                errors.append('Please select a valid role.')

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'users/user_add.html', {
                'roles': roles,
                'counties': counties,
                'organizations': organizations,
                'form_data': request.POST,
            })

        temporary_password = secrets.token_urlsafe(12)
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=temporary_password,
                    first_name=first_name,
                    last_name=last_name,
                    phone_number=phone_number,
                    organization=organization,
                    role=role,
                    is_active=True,
                    is_verified=True,
                    is_email_verified=True,
                    force_password_change=True,
                    approved_by=request.user,
                )
                user.counties.set(counties.filter(id__in=county_ids))

                if not send_registration_email(user, temporary_password):
                    raise RuntimeError('Unable to send the registration email.')

                AuditLog.log(
                    user=request.user,
                    action=AuditLog.Action.CREATE,
                    request=request,
                    model_instance=user,
                    changes={'method': 'administrator_registration'},
                )
        except Exception:
            logger.exception('Administrator user registration failed')
            messages.error(request, 'The user was not created because the registration email could not be sent.')
            return render(request, 'users/user_add.html', {
                'roles': roles,
                'counties': counties,
                'form_data': request.POST,
            })

        messages.success(request, f'User "{user.get_full_name() or user.username}" was created and sent their temporary password.')
        return redirect('users:user_management')

    return render(request, 'users/user_add.html', {'roles': roles, 'counties': counties, 'organizations': organizations})

@login_required
@permission_required('can_manage_users')
def user_edit(request, pk):
    """
    Edit user details - uses database permission
    Allows admins to modify user accounts
    """
    user_obj = get_object_or_404(
        User.objects.select_related('role').prefetch_related('counties'),
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
        organization = Organization.objects.filter(pk=request.POST.get('organization'), is_active=True).first() if request.POST.get('organization') else None
        is_active = request.POST.get('is_active') == 'on'
        is_verified = request.POST.get('is_verified') == 'on'
        role_id = request.POST.get('role')
        county_ids = request.POST.getlist('counties')
        
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
            return render(request, 'users/user_edit.html', {
                'edit_user': user_obj,
                'roles': Role.objects.filter(is_active=True),
                'counties': County.objects.filter(is_active=True),
                'organizations': Organization.objects.filter(is_active=True),
            })
        
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
            changes['organization'] = {'old': str(user_obj.organization or ''), 'new': str(organization or '')}
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
        
        assigned_counties = list(County.objects.filter(id__in=county_ids, is_active=True))
        old_counties = list(user_obj.counties.values_list('name', flat=True))
        new_counties = [county.name for county in assigned_counties]
        if set(old_counties) != set(new_counties):
            changes['counties'] = {'old': old_counties, 'new': new_counties}
        
        # Save user
        user_obj.save()
        user_obj.counties.set(assigned_counties)
        
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
    organizations = Organization.objects.filter(is_active=True)
    
    context = {
        'edit_user': user_obj,
        'counties': counties,
        'roles': roles,
        'organizations': organizations,
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