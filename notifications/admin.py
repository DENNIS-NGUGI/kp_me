from django.contrib import admin
from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'title', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'is_archived', 'created_at']
    search_fields = ['title', 'message', 'user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Recipient', {
            'fields': ('user',)
        }),
        ('Content', {
            'fields': ('title', 'message', 'notification_type')
        }),
        ('Action', {
            'fields': ('action_url', 'action_text')
        }),
        ('Status', {
            'fields': ('is_read', 'is_archived', 'read_at')
        }),
        ('Related Object', {
            'fields': ('content_type', 'object_id')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        return True
    
    def has_delete_permission(self, request, obj=None):
        return True


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'email_submissions', 'email_approvals', 'email_deadlines', 
                    'in_app_submissions', 'in_app_approvals']
    list_filter = ['email_submissions', 'email_approvals', 'email_deadlines']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Email Preferences', {
            'fields': ('email_submissions', 'email_approvals', 'email_deadlines', 'email_reminders')
        }),
        ('In-App Preferences', {
            'fields': ('in_app_submissions', 'in_app_approvals', 'in_app_deadlines', 'in_app_reminders')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
