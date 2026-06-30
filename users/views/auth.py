import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from django.http import JsonResponse
from captcha.models import CaptchaStore
from captcha.helpers import captcha_image_url

from ..models import User, Role, AuditLog, AuthConstants
from ..decorators import permission_required
from ..validators import validate_password_strength, validate_phone_number
from ..utils import send_otp_email, validate_captcha, get_captcha_context

logger = logging.getLogger(__name__)

@never_cache
def login_view(request):
    """Login with OTP for first-time login"""
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_verified:
            return redirect('reports:dashboard')
        return redirect('users:profile')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        captcha_key = request.POST.get('captcha_0', '')
        captcha_value = request.POST.get('captcha_1', '')
        
        # Validate CAPTCHA
        is_valid, error = validate_captcha(captcha_key, captcha_value)
        if not is_valid:
            messages.error(request, error)
            return render(request, 'users/login.html', get_captcha_context())
        
        # Authenticate
        user = authenticate(request, username=username, password=password)
        
        if user is None:
            messages.error(request, 'Invalid username or password.')
            return render(request, 'users/login.html', get_captcha_context())
        
        # Check account lockout
        if user.is_account_locked():
            remaining = user.get_lockout_remaining()
            minutes = int(remaining.total_seconds() / 60) + 1 if remaining else 0
            messages.error(
                request, 
                f'Account is locked. Please try again after {minutes} minutes.'
            )
            return render(request, 'users/login.html', get_captcha_context())
        
        # Check if account is active
        if not user.is_active:
            messages.error(request, 'Account is deactivated. Contact administrator.')
            return render(request, 'users/login.html', get_captcha_context())
        
        # Log login attempt
        AuditLog.log(
            user=user,
            action=AuditLog.Action.LOGIN,
            request=request,
            changes={'method': 'password'}
        )
        
        # Check email verification
        if not user.is_email_verified:
            otp = user.generate_otp()  # Use model method
            email_sent = send_otp_email(user, otp)
            
            if not email_sent:
                messages.warning(
                    request, 
                    'Unable to send verification email. Please contact support.'
                )
            else:
                messages.info(request, 'Please verify your email to complete login.')
            
            request.session['pending_verification_user_id'] = user.id
            return redirect('users:verify_otp')
        
        # Successful login
        user.reset_login_attempts()
        login(request, user)
        
        messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
        
        # Redirect to next parameter
        next_url = request.GET.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        
        return redirect('reports:dashboard')
    
    # GET request
    context = get_captcha_context()
    context.update({
        'site_name': settings.SITE_NAME,
        'allow_registration': getattr(settings, 'ALLOW_REGISTRATION', True),
    })
    return render(request, 'users/login.html', context)

@login_required
def logout_view(request):
    """Logout user"""
    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.LOGOUT,
        request=request
    )
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('users:login')

@never_cache
def register(request):
    """Register a new user with email OTP verification"""
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_verified:
            return redirect('reports:dashboard')
        return redirect('users:profile')
    
    if not getattr(settings, 'ALLOW_REGISTRATION', True):
        messages.error(request, 'Registration is disabled. Contact administrator.')
        return redirect('users:login')
    
    if request.method == 'POST':
        # Extract data
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        role_id = request.POST.get('role')
        organization = request.POST.get('organization', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        terms_accepted = request.POST.get('terms_accepted') == 'on'
        captcha_key = request.POST.get('captcha_0', '')
        captcha_value = request.POST.get('captcha_1', '')
        
        errors = []
        
        # Validate email
        if not email:
            errors.append('Email is required.')
        elif User.objects.filter(email=email).exists():
            errors.append('Email already registered.')
        elif '@' not in email or '.' not in email:
            errors.append('Please enter a valid email address.')
        
        # Validate username
        if not username:
            errors.append('Username is required.')
        elif len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        elif User.objects.filter(username__iexact=username).exists():
            errors.append('Username already exists.')
        elif not username.replace('_', '').replace('-', '').isalnum():
            errors.append('Username can only contain letters, numbers, underscores, and hyphens.')
        
        # Validate password
        if not password1:
            errors.append('Password is required.')
        else:
            password_errors = validate_password_strength(password1)
            if password_errors:
                errors.extend(password_errors)
            elif password1 != password2:
                errors.append('Passwords do not match.')
        
        # Validate phone
        if phone_number and not validate_phone_number(phone_number):
            errors.append('Please enter a valid phone number (e.g., +254712345678).')
        
        # Validate CAPTCHA
        is_valid, error = validate_captcha(captcha_key, captcha_value)
        if not is_valid:
            errors.append(error)
        
        # Validate terms
        if not terms_accepted:
            errors.append('You must accept the Terms & Conditions.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            roles = Role.objects.filter(is_active=True)
            context = get_captcha_context()
            context.update({
                'roles': roles,
                'form_data': {
                    'username': username,
                    'email': email,
                    'organization': organization,
                    'phone_number': phone_number,
                    'first_name': first_name,
                    'last_name': last_name,
                    'role_id': role_id,
                    'terms_accepted': terms_accepted,
                }
            })
            return render(request, 'users/register.html', context)
        
        # Create user
        try:
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
            
            if role_id:
                try:
                    role = Role.objects.get(id=role_id, is_active=True)
                    user.role = role
                    user.save()
                except Role.DoesNotExist:
                    logger.warning(f"Invalid role ID during registration: {role_id}")
            
            # Generate OTP using model method
            otp = user.generate_otp()
            email_sent = send_otp_email(user, otp)
            
            if not email_sent:
                messages.warning(
                    request, 
                    'Account created but failed to send verification email.'
                )
            else:
                messages.info(
                    request, 
                    'Account created! A verification code has been sent to your email.'
                )
            
            AuditLog.log(
                user=user,
                action=AuditLog.Action.CREATE,
                request=request,
                changes={'method': 'registration'}
            )
            
            request.session['pending_verification_user_id'] = user.id
            return redirect('users:verify_otp')
            
        except Exception as e:
            logger.error(f"Registration error: {e}")
            messages.error(request, 'An error occurred during registration.')
            roles = Role.objects.filter(is_active=True)
            context = get_captcha_context()
            context['roles'] = roles
            return render(request, 'users/register.html', context)
    
    # GET request
    roles = Role.objects.filter(is_active=True)
    context = get_captcha_context()
    context.update({
        'roles': roles,
        'site_name': settings.SITE_NAME,
        'allow_registration': getattr(settings, 'ALLOW_REGISTRATION', True),
    })
    return render(request, 'users/register.html', context)

def terms_conditions(request):
    """Terms and Conditions page"""
    return render(request, 'users/terms.html')

@never_cache
def verify_otp(request):
    """Verify OTP for registration or login"""
    user_id = request.session.get('pending_verification_user_id')
    if not user_id:
        messages.error(request, 'No pending verification found.')
        return redirect('users:login')
    
    user = get_object_or_404(User, id=user_id)
    
    if user.is_email_verified:
        messages.info(request, 'Your email is already verified.')
        login(request, user)
        if 'pending_verification_user_id' in request.session:
            del request.session['pending_verification_user_id']
        return redirect('reports:dashboard')
    
    if request.method == 'POST':
        otp = request.POST.get('otp', '').strip()
        
        if not otp:
            messages.error(request, 'Please enter the verification code.')
            return render(request, 'users/verify_otp.html', {'email': user.email})
        
        if not otp.isdigit() or len(otp) != AuthConstants.OTP_LENGTH:
            messages.error(request, f'Please enter a valid {AuthConstants.OTP_LENGTH}-digit code.')
            return render(request, 'users/verify_otp.html', {'email': user.email})
        
        if user.verify_otp(otp):
            user.is_verified = True
            user.is_email_verified = True
            user.email_verified_at = timezone.now()
            user.clear_otp()
            user.save()
            
            AuditLog.log(
                user=user,
                action=AuditLog.Action.APPROVE,
                request=request,
                changes={'type': 'email_verification'}
            )
            
            login(request, user)
            
            if 'pending_verification_user_id' in request.session:
                del request.session['pending_verification_user_id']
            
            messages.success(request, 'Email verified successfully! Welcome to KP M&E System.')
            return redirect('reports:dashboard')
        else:
            messages.error(request, 'Invalid or expired verification code. Please try again.')
            return render(request, 'users/verify_otp.html', {'email': user.email})
    
    return render(request, 'users/verify_otp.html', {'email': user.email})

@require_http_methods(["POST"])
def resend_otp(request):
    """Resend OTP code"""
    user_id = request.session.get('pending_verification_user_id')
    if not user_id:
        messages.error(request, 'No pending verification found.')
        return redirect('users:login')
    
    user = get_object_or_404(User, id=user_id)
    
    # Rate limiting
    if user.otp_created_at:
        time_since_last = timezone.now() - user.otp_created_at
        if time_since_last.total_seconds() < AuthConstants.OTP_RESEND_COOLDOWN:
            messages.warning(request, 'Please wait 1 minute before requesting another code.')
            return redirect('users:verify_otp')
    
    # Generate and send new OTP using model method
    otp = user.generate_otp()
    email_sent = send_otp_email(user, otp)
    
    if email_sent:
        messages.success(request, 'A new verification code has been sent to your email.')
    else:
        messages.error(request, 'Failed to send verification email. Please try again.')
    
    return redirect('users:verify_otp')

def ajax_captcha_refresh(request):
    """Custom captcha refresh view - returns new captcha data"""
    if request.method == 'GET':
        new_key = CaptchaStore.generate_key()
        return JsonResponse({
            'key': new_key,
            'image_url': captcha_image_url(new_key),
        })
    return JsonResponse({'error': 'Invalid request'}, status=400)