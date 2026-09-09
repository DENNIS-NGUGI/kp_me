from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_otp_email(user, otp):
    """Send OTP via email with improved deliverability"""
    subject = 'KPPIMES - Your Verification Code'
    
    # Plain text version
    text_message = f"""
    Dear {user.get_full_name() or user.username},

    Your verification code for KPPIMES is: {otp}

    This code will expire in 10 minutes.

    If you didn't request this code, please ignore this email.

    ---
    KPPIMES
    Kenya Population Programme
    """
    
    # HTML version
    try:
        html_message = render_to_string('users/otp_email.html', {
            'user': user,
            'otp': otp,
            'expiry_minutes': 10,
            'site_name': settings.SITE_NAME,
        })
    except Exception as e:
        logger.warning(f"Failed to render OTP email template: {e}")
        html_message = None
    
    try:
        send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"OTP email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP email to {user.email}: {e}")
        return False


def send_registration_email(user, temporary_password):
    """Send an administrator-created user's initial sign-in credentials."""
    subject = 'KPPIMES - Your account has been created'
    message = f"""Dear {user.get_full_name() or user.username},

An administrator has created your KPPIMES account.

Username: {user.username}
Temporary password: {temporary_password}

Sign in at {settings.SITE_URL or 'the KPPIMES login page'}. You will receive a verification code by email and must change this temporary password before you can use the system.

KPPIMES
Kenya Population Programme
"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Registration email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send registration email to {user.email}: {e}")
        return False