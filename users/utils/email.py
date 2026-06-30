from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_otp_email(user, otp):
    """Send OTP via email with improved deliverability"""
    subject = 'KP M&E System - Your Verification Code'
    
    # Plain text version
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