import random
import string
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone


def generate_otp():
    """Generate a 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))


def send_otp_email(user, otp):
    """Send OTP via email"""
    subject = 'Your KP M&E System Verification Code'
    html_message = render_to_string('users/otp_email.html', {
        'user': user,
        'otp': otp,
    })
    try:
        send_mail(
            subject=subject,
            message=f'Your verification code is: {otp}',
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
