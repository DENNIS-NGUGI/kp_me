from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from core.models import County
from indicators.models import Indicator, ThematicArea
from data_entry.models import DataEntry
from .models import Role
from users.decorators import view_reports_required, admin_required, ncpd_or_admin_required
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from captcha.models import CaptchaStore
from captcha.helpers import captcha_image_url
import random
import string
from django.http import JsonResponse

User = get_user_model()


# ===== OTP UTILITY FUNCTIONS =====

def generate_otp():
    """Generate a 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))

def send_otp_email(user, otp):
    """Send OTP via email - improved deliverability"""
    subject = 'KP M&E System - Your Verification Code'
    
    # Plain text version (better for spam filters)
    text_message = f"""
    Dear {user.get_full_name() or user.username},

    Your verification code for KP M&E System is: {otp}

    This code will expire in 10 minutes.

    If you didn't request this code, please ignore this email.

    ---
    KP M&E System
    Kenya Population Programme
    """
    
    # HTML version
    html_message = render_to_string('users/otp_email.html', {
        'user': user,
        'otp': otp,
    })
    
    try:
        send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"OTP email error: {e}")
        return False

def validate_password(password):
    """Validate password strength"""
    errors = []
    if len(password) < 8:
        errors.append('Password must be at least 8 characters.')
    if not any(c.isdigit() for c in password):
        errors.append('Password must contain at least one number.')
    if not any(c.isupper() for c in password):
        errors.append('Password must contain at least one uppercase letter.')
    if not any(c.islower() for c in password):
        errors.append('Password must contain at least one lowercase letter.')
    return errors

def login_view(request):
    """Login with OTP for first-time login"""
    # If already logged in, redirect
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_verified:
            return redirect('reports:dashboard')
        else:
            return redirect('users:profile')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        captcha_key = request.POST.get('captcha_0', '')
        captcha_value = request.POST.get('captcha_1', '')
        
        # ===== CAPTCHA VALIDATION =====
        if not captcha_key or not captcha_value:
            messages.error(request, 'Captcha is required.')
            captcha_key = CaptchaStore.generate_key()
            captcha_image = captcha_image_url(captcha_key)
            return render(request, 'users/login.html', {
                'captcha_key': captcha_key,
                'captcha_image': captcha_image,
            })
        
        try:
            stored_captcha = CaptchaStore.objects.get(hashkey=captcha_key)
            # Case-insensitive comparison
            if stored_captcha.response.lower() != captcha_value.lower():
                messages.error(request, 'Invalid captcha. Please try again.')
                captcha_key = CaptchaStore.generate_key()
                captcha_image = captcha_image_url(captcha_key)
                return render(request, 'users/login.html', {
                    'captcha_key': captcha_key,
                    'captcha_image': captcha_image,
                })
            # Valid captcha - delete it
            stored_captcha.delete()
        except CaptchaStore.DoesNotExist:
            messages.error(request, 'Invalid captcha. Please try again.')
            captcha_key = CaptchaStore.generate_key()
            captcha_image = captcha_image_url(captcha_key)
            return render(request, 'users/login.html', {
                'captcha_key': captcha_key,
                'captcha_image': captcha_image,
            })
        except Exception:
            messages.error(request, 'Captcha error. Please try again.')
            captcha_key = CaptchaStore.generate_key()
            captcha_image = captcha_image_url(captcha_key)
            return render(request, 'users/login.html', {
                'captcha_key': captcha_key,
                'captcha_image': captcha_image,
            })
        
        # ===== AUTHENTICATION =====
        user = authenticate(request, username=username, password=password)
        
        if user is None:
            messages.error(request, 'Invalid username or password.')
            captcha_key = CaptchaStore.generate_key()
            captcha_image = captcha_image_url(captcha_key)
            return render(request, 'users/login.html', {
                'captcha_key': captcha_key,
                'captcha_image': captcha_image,
            })
        
        # ===== ACCOUNT LOCK CHECK =====
        if user.is_account_locked():
            messages.error(request, 'Account is locked due to too many failed attempts. Please try again after 30 minutes.')
            captcha_key = CaptchaStore.generate_key()
            captcha_image = captcha_image_url(captcha_key)
            return render(request, 'users/login.html', {
                'captcha_key': captcha_key,
                'captcha_image': captcha_image,
            })
        
        # ===== ACCOUNT ACTIVE CHECK =====
        if not user.is_active:
            messages.error(request, 'Account is deactivated. Please contact administrator.')
            captcha_key = CaptchaStore.generate_key()
            captcha_image = captcha_image_url(captcha_key)
            return render(request, 'users/login.html', {
                'captcha_key': captcha_key,
                'captcha_image': captcha_image,
            })
        
        # ===== EMAIL VERIFICATION CHECK =====
        if not user.is_email_verified:
            otp = generate_otp()
            user.otp_secret = otp
            user.otp_created_at = timezone.now()
            user.save()
            
            send_otp_email(user, otp)
            
            request.session['pending_verification_user_id'] = user.id
            messages.info(request, 'Please verify your email to complete login.')
            return redirect('users:verify_otp')
        
        # ===== SUCCESSFUL LOGIN =====
        user.reset_login_attempts()
        login(request, user)
        messages.success(request, f'Welcome back, {user.username}!')
        return redirect('reports:dashboard')
    
    # ===== GET REQUEST =====
    captcha_key = CaptchaStore.generate_key()
    captcha_image = captcha_image_url(captcha_key)
    return render(request, 'users/login.html', {
        'captcha_key': captcha_key,
        'captcha_image': captcha_image,
    })

def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('users:login')

# def register(request):
#     """Register a new user with email OTP verification"""
#     # If user is already logged in, redirect
#     if request.user.is_authenticated:
#         if request.user.is_superuser or request.user.is_verified:
#             return redirect('reports:dashboard')
#         else:
#             return redirect('users:profile')
    
#     if request.method == 'POST':
#         username = request.POST.get('username', '').strip()
#         email = request.POST.get('email', '').strip()
#         password1 = request.POST.get('password1', '')
#         password2 = request.POST.get('password2', '')
#         role_id = request.POST.get('role')
#         organization = request.POST.get('organization', '').strip()
#         phone_number = request.POST.get('phone_number', '').strip()
#         first_name = request.POST.get('first_name', '').strip()
#         last_name = request.POST.get('last_name', '').strip()
#         captcha_key = request.POST.get('captcha_0', '')
#         captcha_value = request.POST.get('captcha_1', '')
        
#         # ===== VALIDATION =====
#         errors = []
        
#         # Email validation
#         if not email:
#             errors.append('Email is required.')
#         elif User.objects.filter(email=email).exists():
#             errors.append('Email already registered.')
        
#         # Username validation
#         if not username:
#             errors.append('Username is required.')
#         elif len(username) < 3:
#             errors.append('Username must be at least 3 characters.')
#         elif User.objects.filter(username=username).exists():
#             errors.append('Username already exists.')
        
#         # Password validation
#         if not password1:
#             errors.append('Password is required.')
#         else:
#             password_errors = validate_password(password1)
#             if password_errors:
#                 errors.extend(password_errors)
#             elif password1 != password2:
#                 errors.append('Passwords do not match.')
        
#         # ===== CAPTCHA VALIDATION =====
#         if not captcha_key or not captcha_value:
#             errors.append('Captcha is required.')
#         else:
#             try:
#                 captcha = CaptchaStore.objects.get(hashkey=captcha_key)
#                 if captcha.response != captcha_value:
#                     errors.append('Invalid captcha. Please try again.')
#                 else:
#                     # Valid captcha - delete it
#                     captcha.delete()
#             except CaptchaStore.DoesNotExist:
#                 errors.append('Invalid captcha. Please try again.')
        
#         if errors:
#             for error in errors:
#                 messages.error(request, error)
#             roles = Role.objects.filter(is_active=True)
#             captcha_key = CaptchaStore.generate_key()
#             captcha_image = captcha_image_url(captcha_key)
#             return render(request, 'users/register.html', {
#                 'roles': roles,
#                 'captcha_key': captcha_key,
#                 'captcha_image': captcha_image,
#             })

        
#         # ===== CREATE USER =====
#         user = User.objects.create_user(
#             username=username,
#             email=email,
#             password=password1,
#             organization=organization,
#             phone_number=phone_number,
#             first_name=first_name,
#             last_name=last_name,
#             is_active=True,
#             is_verified=False,
#             is_email_verified=False,
#         )
        
#         # Assign role
#         if role_id:
#             try:
#                 role = Role.objects.get(id=role_id)
#                 user.role = role
#                 user.save()
#             except Role.DoesNotExist:
#                 pass
        
#         # ===== GENERATE AND SEND OTP =====
#         otp = generate_otp()
#         user.otp_secret = otp
#         user.otp_created_at = timezone.now()
#         user.save()
        
#         email_sent = send_otp_email(user, otp)
        
#         if not email_sent:
#             messages.warning(request, 'Failed to send verification email. Please contact support.')
        
#         # Store user ID in session for OTP verification
#         request.session['pending_verification_user_id'] = user.id
        
#         messages.info(request, 'A verification code has been sent to your email. Please verify to complete registration.')
#         return redirect('users:verify_otp')
    
#     # ===== GET REQUEST =====
#     roles = Role.objects.filter(is_active=True)
#     captcha_key = CaptchaStore.generate_key()
#     captcha_image = captcha_image_url(captcha_key)
#     return render(request, 'users/register.html', {
#         'roles': roles,
#         'captcha_key': captcha_key,
#         'captcha_image': captcha_image,
#     })

def register(request):
    """Register a new user with email OTP verification"""
    # If user is already logged in, redirect
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_verified:
            return redirect('reports:dashboard')
        else:
            return redirect('users:profile')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        role_id = request.POST.get('role')
        organization = request.POST.get('organization', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        captcha_key = request.POST.get('captcha_0', '')
        captcha_value = request.POST.get('captcha_1', '')
        
        # ===== VALIDATION =====
        errors = []
        
        # Email validation
        if not email:
            errors.append('Email is required.')
        elif User.objects.filter(email=email).exists():
            errors.append('Email already registered.')
        
        # Username validation
        if not username:
            errors.append('Username is required.')
        elif len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        elif User.objects.filter(username=username).exists():
            errors.append('Username already exists.')
        
        # Password validation
        if not password1:
            errors.append('Password is required.')
        else:
            password_errors = validate_password(password1)
            if password_errors:
                errors.extend(password_errors)
            elif password1 != password2:
                errors.append('Passwords do not match.')
        
        # ===== CAPTCHA VALIDATION =====
        if not captcha_key or not captcha_value:
            errors.append('Captcha is required.')
        else:
            try:
                stored_captcha = CaptchaStore.objects.get(hashkey=captcha_key)
                # Case-insensitive comparison
                if stored_captcha.response.lower() != captcha_value.lower():
                    errors.append('Invalid captcha. Please try again.')
                else:
                    # Valid captcha - delete it
                    stored_captcha.delete()
            except CaptchaStore.DoesNotExist:
                errors.append('Invalid captcha. Please try again.')
            except Exception:
                errors.append('Captcha error. Please try again.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            roles = Role.objects.filter(is_active=True)
            captcha_key = CaptchaStore.generate_key()
            captcha_image = captcha_image_url(captcha_key)
            return render(request, 'users/register.html', {
                'roles': roles,
                'captcha_key': captcha_key,
                'captcha_image': captcha_image,
            })
        
        # ===== CREATE USER =====
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            organization=organization,
            phone_number=phone_number,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            is_verified=False,
            is_email_verified=False,
        )
        
        # Assign role
        if role_id:
            try:
                role = Role.objects.get(id=role_id)
                user.role = role
                user.save()
            except Role.DoesNotExist:
                pass
        
        # ===== GENERATE AND SEND OTP =====
        otp = generate_otp()
        user.otp_secret = otp
        user.otp_created_at = timezone.now()
        user.save()
        
        email_sent = send_otp_email(user, otp)
        
        if not email_sent:
            messages.warning(request, 'Failed to send verification email. Please contact support.')
        
        # Store user ID in session for OTP verification
        request.session['pending_verification_user_id'] = user.id
        
        messages.info(request, 'A verification code has been sent to your email. Please verify to complete registration.')
        return redirect('users:verify_otp')
    
    # ===== GET REQUEST =====
    roles = Role.objects.filter(is_active=True)
    captcha_key = CaptchaStore.generate_key()
    captcha_image = captcha_image_url(captcha_key)
    return render(request, 'users/register.html', {
        'roles': roles,
        'captcha_key': captcha_key,
        'captcha_image': captcha_image,
    })

def verify_otp(request):
    """Verify OTP for registration or login"""
    # Check if user has pending verification
    user_id = request.session.get('pending_verification_user_id')
    if not user_id:
        messages.error(request, 'No pending verification found.')
        return redirect('users:login')
    
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        otp = request.POST.get('otp', '').strip()
        
        if not otp:
            messages.error(request, 'Please enter the verification code.')
            return render(request, 'users/verify_otp.html', {'email': user.email})
        
        if user.verify_otp(otp):
            # OTP verified - mark user as verified
            user.is_verified = True
            user.is_email_verified = True
            user.email_verified_at = timezone.now()
            user.otp_secret = None
            user.otp_created_at = None
            user.save()
            
            # Log the user in
            login(request, user)
            
            # Clear session
            if 'pending_verification_user_id' in request.session:
                del request.session['pending_verification_user_id']
            
            messages.success(request, 'Email verified successfully! Welcome to KP M&E System.')
            return redirect('reports:dashboard')
        else:
            messages.error(request, 'Invalid or expired verification code. Please try again.')
            return render(request, 'users/verify_otp.html', {'email': user.email})
    
    # GET request - show OTP form
    return render(request, 'users/verify_otp.html', {'email': user.email})

def resend_otp(request):
    """Resend OTP code"""
    user_id = request.session.get('pending_verification_user_id')
    if not user_id:
        messages.error(request, 'No pending verification found.')
        return redirect('users:login')
    
    user = get_object_or_404(User, id=user_id)
    
    # Generate new OTP
    otp = generate_otp()
    user.otp_secret = otp
    user.otp_created_at = timezone.now()
    user.save()
    
    # Send OTP email
    if send_otp_email(user, otp):
        messages.success(request, 'A new verification code has been sent to your email.')
    else:
        messages.error(request, 'Failed to send verification email. Please try again.')
    
    return redirect('users:verify_otp')

def ajax_captcha_refresh(request):
    """Custom captcha refresh view - returns new captcha data"""
    if request.method == 'GET':
        new_key = CaptchaStore.generate_key()
        to_json_response = {
            'key': new_key,
            'image_url': captcha_image_url(new_key),
        }
        return JsonResponse(to_json_response)
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def profile(request):
    return render(request, 'users/profile.html', {'user': request.user})

@login_required
def edit_profile(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.phone_number = request.POST.get('phone_number', user.phone_number)
        user.organization = request.POST.get('organization', user.organization)
        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('users:profile')
    return render(request, 'users/edit_profile.html', {'user': request.user})

# ===== USER MANAGEMENT VIEWS =====
@login_required
@admin_required
def user_management(request):
    """Manage users"""
    users = User.objects.all().order_by('-date_joined')
    
    # Filters
    role_filter = request.GET.get('role')
    county_filter = request.GET.get('county')
    
    if role_filter:
        users = users.filter(role_id=role_filter)
    if county_filter:
        users = users.filter(county_id=county_filter)
    
    # Get roles and counties for filters
    roles = Role.objects.filter(is_active=True)
    counties = County.objects.filter(is_active=True)
    
    context = {
        'users': users,
        'roles': roles,
        'counties': counties,
        'selected_role': role_filter,
        'selected_county': county_filter,
    }
    return render(request, 'users/user_management.html', context)

@login_required
@admin_required
def user_edit(request, pk):
    """Edit user details"""
    user_obj = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        user_obj.first_name = request.POST.get('first_name', '')
        user_obj.last_name = request.POST.get('last_name', '')
        user_obj.email = request.POST.get('email', '')
        user_obj.phone_number = request.POST.get('phone_number', '')
        user_obj.organization = request.POST.get('organization', '')
        user_obj.is_active = request.POST.get('is_active') == 'on'
        user_obj.is_verified = request.POST.get('is_verified') == 'on'
        
        role_id = request.POST.get('role')
        if role_id:
            try:
                user_obj.role_id = role_id
            except Role.DoesNotExist:
                pass
        else:
            user_obj.role = None
        
        county_id = request.POST.get('county')
        if county_id:
            user_obj.county_id = county_id
        else:
            user_obj.county = None
        
        user_obj.save()
        messages.success(request, f'User "{user_obj.username}" updated successfully!')
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
@admin_required
def user_toggle_status(request, pk):
    """Toggle user active status"""
    user_obj = get_object_or_404(User, pk=pk)
    user_obj.is_active = not user_obj.is_active
    user_obj.save()
    
    status = 'activated' if user_obj.is_active else 'deactivated'
    messages.success(request, f'User "{user_obj.username}" {status} successfully!')
    return redirect('users:user_management')

@login_required
@admin_required
def user_delete(request, pk):
    """Delete a user"""
    user_obj = get_object_or_404(User, pk=pk)
    
    if user_obj.is_superuser:
        messages.warning(request, 'Cannot delete superuser.')
        return redirect('users:user_management')
    
    if request.method == 'POST':
        username = user_obj.username
        user_obj.delete()
        messages.success(request, f'User "{username}" deleted successfully!')
        return redirect('users:user_management')
    
    return render(request, 'users/user_delete.html', {'user': user_obj})

# ===== ROLE MANAGEMENT VIEWS =====
@login_required
@admin_required
def role_list(request):
    """List all roles with their permissions"""
    roles = Role.objects.all().order_by('name')
    
    # Get all available modules for display
    modules = [
        'dashboard', 'data_entry', 'indicators', 'reports', 
        'partners', 'projects', 'users', 'settings', 'audit_log'
    ]
    actions = ['view', 'add', 'change', 'delete']
    
    # Build role data with permission codenames
    role_data = []
    for role in roles:
        perm_codenames = [p.codename for p in role.permissions.all()]
        role_data.append({
            'id': role.id,
            'name': role.name,
            'description': role.description,
            'is_system': role.is_system,
            'is_active': role.is_active,
            'created_at': role.created_at,
            'perm_codenames': perm_codenames,
            'user_count': role.users.count(),
        })
    
    context = {
        'roles': role_data,
        'modules': modules,
        'actions': actions,
    }
    return render(request, 'users/roles.html', context)

@login_required
@admin_required
def role_add(request):
    """Add a new role"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        
        if not name:
            messages.error(request, 'Role name is required.')
            return render(request, 'users/role_form.html')
        
        if Role.objects.filter(name=name).exists():
            messages.error(request, f'Role "{name}" already exists.')
            return render(request, 'users/role_form.html')
        
        role = Role.objects.create(
            name=name,
            description=description,
            is_system=False,
            is_active=True
        )
        
        # Assign permissions if any selected
        permission_ids = request.POST.getlist('permissions')
        if permission_ids:
            permissions = Permission.objects.filter(id__in=permission_ids)
            role.permissions.set(permissions)
        
        messages.success(request, f'Role "{name}" created successfully!')
        return redirect('users:role_list')
    
    # Get all permissions grouped by module
    all_perms = Permission.objects.all().order_by('content_type__app_label', 'codename')
    modules = {}
    for perm in all_perms:
        parts = perm.codename.split('_', 1)
        if len(parts) == 2:
            action, module = parts
            if module not in modules:
                modules[module] = {'name': module.title(), 'permissions': []}
            modules[module]['permissions'].append({
                'id': perm.id,
                'codename': perm.codename,
                'name': perm.name,
                'action': action
            })
    
    context = {'modules': modules}
    return render(request, 'users/role_form.html', context)

@login_required
@admin_required
def role_edit(request, pk):
    """Edit a role - FULL access for superusers and admins"""
    role = get_object_or_404(Role, pk=pk)
    
    if request.method == 'POST':
        # Get form data
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        
        # Check if name is taken (except for this role)
        if Role.objects.filter(name=name).exclude(pk=pk).exists():
            messages.error(request, f'Role "{name}" already exists.')
            return render(request, 'users/role_form.html', {'role': role})
        
        # Update all fields (including permissions)
        role.name = name
        role.description = description
        role.is_active = is_active
        
        # Update permissions (allowed for ALL roles since user is superuser/admin)
        permission_ids = request.POST.getlist('permissions')
        if permission_ids:
            permissions = Permission.objects.filter(id__in=permission_ids)
            role.permissions.set(permissions)
        else:
            role.permissions.clear()
        
        role.save()
        
        messages.success(request, f'Role "{role.name}" updated successfully!')
        return redirect('users:role_list')
    
    # GET - display form
    # Get all permissions grouped by module
    all_perms = Permission.objects.all().order_by('content_type__app_label', 'codename')
    modules = {}
    for perm in all_perms:
        parts = perm.codename.split('_', 1)
        if len(parts) == 2:
            action, module = parts
            if module not in modules:
                modules[module] = {'name': module.title(), 'permissions': []}
            modules[module]['permissions'].append({
                'id': perm.id,
                'codename': perm.codename,
                'name': perm.name,
                'action': action,
                'checked': perm in role.permissions.all()
            })
    
    context = {
        'role': role,
        'modules': modules,
    }
    return render(request, 'users/role_form.html', context)

@login_required
@admin_required
def role_delete(request, pk):
    """Delete a role"""
    role = get_object_or_404(Role, pk=pk)
    
    if role.is_system:
        messages.warning(request, 'System roles cannot be deleted.')
        return redirect('users:role_list')
    
    if request.method == 'POST':
        role_name = role.name
        role.delete()
        messages.success(request, f'Role "{role_name}" deleted successfully!')
        return redirect('users:role_list')
    
    return render(request, 'users/role_delete.html', {'role': role})

@login_required
@admin_required
def role_update_permissions(request, pk):
    """Update permissions for a role"""
    role = get_object_or_404(Role, pk=pk)
    
    if role.is_system:
        messages.warning(request, 'System roles cannot be modified.')
        return redirect('users:role_list')
    
    if request.method == 'POST':
        # Get selected permission codenames
        permission_codenames = request.POST.getlist('permissions')
        
        if permission_codenames:
            permissions = Permission.objects.filter(codename__in=permission_codenames)
            role.permissions.set(permissions)
            messages.success(request, f'Permissions for "{role.name}" updated successfully!')
        else:
            role.permissions.clear()
            messages.info(request, f'All permissions removed from "{role.name}".')
        
        return redirect('users:role_list')
    
    return redirect('users:role_list')


