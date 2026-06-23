from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class Notification(models.Model):
    """In-app notification system"""
    
    NOTIFICATION_TYPES = (
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('approval', 'Approval'),
        ('rejection', 'Rejection'),
        ('submission', 'Submission'),
        ('deadline', 'Deadline'),
    )
    
    # Recipient - allow null for system notifications
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='notifications',
        null=True,  # Allow null
        blank=True  # Allow blank in forms
    )
    
    # Content
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='info')
    
    # Action link (optional)
    action_url = models.CharField(max_length=200, blank=True, help_text="URL to navigate when clicked")
    action_text = models.CharField(max_length=50, blank=True, help_text="Button text for action")
    
    # Status
    is_read = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Related object (optional)
    content_type = models.CharField(max_length=100, blank=True, help_text="Model name e.g., DataEntry")
    object_id = models.CharField(max_length=100, blank=True, help_text="Object ID")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username if self.user else 'System'} - {self.title[:50]}"
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    def mark_as_unread(self):
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save()

class NotificationPreference(models.Model):
    """User preferences for notifications"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Email preferences
    email_submissions = models.BooleanField(default=True, help_text="Receive email for submissions")
    email_approvals = models.BooleanField(default=True, help_text="Receive email for approvals/rejections")
    email_deadlines = models.BooleanField(default=True, help_text="Receive email for deadlines")
    email_reminders = models.BooleanField(default=True, help_text="Receive email reminders")
    
    # In-app preferences
    in_app_submissions = models.BooleanField(default=True)
    in_app_approvals = models.BooleanField(default=True)
    in_app_deadlines = models.BooleanField(default=True)
    in_app_reminders = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} Notification Preferences"
