from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.db.models import Q
from .models import Notification, NotificationPreference

User = get_user_model()

def create_notification(user, title, message, notification_type='info', 
                        action_url='', action_text='', content_type='', object_id=''):
    """
    Create an in-app notification for a user
    """
    if not user:
        return Notification.objects.create(
            user=None,
            title=title,
            message=message,
            notification_type=notification_type,
            action_url=action_url,
            action_text=action_text,
            content_type=content_type,
            object_id=object_id
        )
    
    # Check if user has in-app preferences for this type
    try:
        prefs = NotificationPreference.objects.get(user=user)
        if notification_type in ['submission', 'approval', 'rejection']:
            if not prefs.in_app_submissions:
                return None
    except NotificationPreference.DoesNotExist:
        pass
    
    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        action_url=action_url,
        action_text=action_text,
        content_type=content_type,
        object_id=object_id
    )
    
    # Send email notification
    send_email_notification(
        user, 
        title, 
        message, 
        notification_type, 
        action_url=action_url, 
        action_text=action_text
    )
    
    return notification

def send_email_notification(user, subject, message, notification_type='info', action_url='', action_text='View'):
    """
    Send email notification to a user
    """
    if not user or not user.email:
        return False
    
    # Check user's email preferences
    try:
        prefs = NotificationPreference.objects.get(user=user)
        if notification_type in ['submission', 'approval', 'rejection']:
            if not prefs.email_submissions:
                return False
    except NotificationPreference.DoesNotExist:
        pass
    
    html_message = render_to_string('notifications/email_template.html', {
        'user': user,
        'subject': subject,
        'message': message,
        'notification_type': notification_type,
        'site_name': 'KP M&E System',
        'site_url': settings.SITE_URL,
        'action_url': action_url,
        'action_text': action_text,
    })
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Email send error: {e}")
        return False

def notify_submission(entry, user):
    """Notify when data is submitted"""
    if not user:
        return
    
    detail_url = reverse('data_entry:detail', kwargs={'pk': entry.id})
    pending_url = reverse('data_entry:pending')
    
    # Notification for the submitter
    create_notification(
        user=user,
        title='Data Submitted Successfully',
        message=f'Your data for {entry.indicator.code} - {entry.quarter.name} has been submitted for approval.',
        notification_type='submission',
        action_url=detail_url,
        action_text='View Entry',
        content_type='DataEntry',
        object_id=str(entry.id)
    )
    
    approvers = User.objects.filter(
        Q(is_superuser=True) | 
        Q(role__permissions__codename='can_approve_data')
    ).distinct()
    
    for approver in approvers:
        if approver.id == user.id:
            continue
            
        create_notification(
            user=approver,
            title='New Data Submission',
            message=f'{user.username} submitted data for {entry.county.name} - {entry.quarter.name}',
            notification_type='submission',
            action_url=pending_url,
            action_text='Review',
            content_type='DataEntry',
            object_id=str(entry.id)
        )

def notify_approval(entry, approver):
    """Notify when data is approved"""
    detail_url = reverse('data_entry:detail', kwargs={'pk': entry.id})
    
    if not entry.submitted_by:
        create_notification(
            user=None,
            title='Data Approved',
            message=f'Data for {entry.indicator.code} - {entry.quarter.name} was approved by {approver.username}.',
            notification_type='approval',
            action_url=detail_url,
            action_text='View Entry',
            content_type='DataEntry',
            object_id=str(entry.id)
        )
        return
    
    create_notification(
        user=entry.submitted_by,
        title='Data Approved',
        message=f'Your data for {entry.indicator.code} - {entry.quarter.name} has been approved by {approver.username}.',
        notification_type='approval',
        action_url=detail_url,
        action_text='View Entry',
        content_type='DataEntry',
        object_id=str(entry.id)
    )

def notify_rejection(entry, approver, reason):
    """Notify when data is rejected"""
    edit_url = reverse('data_entry:edit', kwargs={'pk': entry.id})
    
    if not entry.submitted_by:
        create_notification(
            user=None,
            title='Data Rejected',
            message=f'Data for {entry.indicator.code} - {entry.quarter.name} was rejected. Reason: {reason}',
            notification_type='rejection',
            action_url=edit_url,
            action_text='Edit & Resubmit',
            content_type='DataEntry',
            object_id=str(entry.id)
        )
        return
    
    create_notification(
        user=entry.submitted_by,
        title='Data Rejected',
        message=f'Your data for {entry.indicator.code} - {entry.quarter.name} was rejected. Reason: {reason}',
        notification_type='rejection',
        action_url=edit_url,
        action_text='Edit & Resubmit',
        content_type='DataEntry',
        object_id=str(entry.id)
    )

def notify_deadline_reminder(user, quarter, days_left):
    """Notify about upcoming deadlines"""
    create_notification(
        user=user,
        title='Submission Deadline Approaching',
        message=f'The deadline for {quarter.name} is in {days_left} days. Please submit your data.',
        notification_type='deadline',
        action_url=reverse('data_entry:list'),
        action_text='Submit Data',
        content_type='Quarter',
        object_id=str(quarter.id)
    )

def notify_missing_submission(user, quarter):
    """Notify about missing submissions"""
    create_notification(
        user=user,
        title='Missing Data Submission',
        message=f'You have not submitted data for {quarter.name}. Please submit as soon as possible.',
        notification_type='warning',
        action_url=reverse('data_entry:list'),
        action_text='Submit Now',
        content_type='Quarter',
        object_id=str(quarter.id)
    )