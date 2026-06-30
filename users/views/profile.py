import logging
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError

from ..models import User, AuditLog
from ..validators import validate_phone_number

logger = logging.getLogger(__name__)

@login_required
def profile(request):
    """
    User profile page
    Displays user information and statistics
    """
    user = request.user
    
    # Get user statistics
    context = {
        'user': user,
        'user_full_name': user.get_full_name(),
        'role_display': user.get_role_display(),
        'is_county_user': user.is_county_user,
        'is_ncpd_user': user.is_ncpd_user,
        'is_admin_user': user.is_admin_user,
        'login_count': user.audit_logs.filter(
            action=AuditLog.Action.LOGIN
        ).count(),
        'last_login': user.last_login,
        'member_since': user.date_joined,
        'email_verified': user.is_email_verified,
        'account_verified': user.is_verified,
    }
    
    # Add county info if county user
    if user.county:
        context['county_name'] = user.county.name
    
    return render(request, 'users/profile.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def edit_profile(request):
    """
    Edit user profile
    Allows users to update their personal information
    """
    user = request.user
    
    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone_number = request.POST.get('phone_number', '').strip()
        organization = request.POST.get('organization', '').strip()
        
        errors = []
        changes = {}
        
        # Validate email
        if email:
            if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                errors.append('Email already in use by another account.')
        else:
            errors.append('Email is required.')
        
        # Validate phone number
        if phone_number and not validate_phone_number(phone_number):
            errors.append('Please enter a valid phone number (e.g., +254712345678).')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'users/edit_profile.html', {'user': user})
        
        # Track changes for audit log
        if user.first_name != first_name:
            changes['first_name'] = {'old': user.first_name, 'new': first_name}
            user.first_name = first_name
        
        if user.last_name != last_name:
            changes['last_name'] = {'old': user.last_name, 'new': last_name}
            user.last_name = last_name
        
        if user.email != email:
            changes['email'] = {'old': user.email, 'new': email}
            user.email = email
        
        if user.phone_number != phone_number:
            changes['phone_number'] = {'old': user.phone_number, 'new': phone_number}
            user.phone_number = phone_number
        
        if user.organization != organization:
            changes['organization'] = {'old': user.organization, 'new': organization}
            user.organization = organization
        
        # Save user
        user.save()
        
        # Log the changes
        if changes:
            AuditLog.log(
                user=user,
                action=AuditLog.Action.UPDATE,
                request=request,
                model_instance=user,
                changes=changes
            )
            messages.success(request, 'Profile updated successfully!')
        else:
            messages.info(request, 'No changes were made.')
        
        return redirect('users:profile')
    
    return render(request, 'users/edit_profile.html', {'user': user})

@login_required
def permission_denied(request):
    """
    Permission denied page
    Shown when a user tries to access a page they don't have permission for
    """
    return render(request, 'users/permission_denied.html', status=403)

@login_required
def change_password(request):
    """
    Change user password
    Allows users to change their password with validation
    """
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password1 = request.POST.get('new_password1', '')
        new_password2 = request.POST.get('new_password2', '')
        
        # Verify current password
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return render(request, 'users/change_password.html')
        
        # Validate new password
        from ..validators import validate_password_strength
        errors = validate_password_strength(new_password1)
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'users/change_password.html')
        
        if new_password1 != new_password2:
            messages.error(request, 'New passwords do not match.')
            return render(request, 'users/change_password.html')
        
        # Change password
        request.user.set_password(new_password1)
        request.user.save()
        
        # Log password change
        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.UPDATE,
            request=request,
            model_instance=request.user,
            changes={'password': 'changed'}
        )
        
        messages.success(request, 'Password changed successfully!')
        return redirect('users:profile')
    
    return render(request, 'users/change_password.html')