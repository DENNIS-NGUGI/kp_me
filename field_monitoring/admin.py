"""
Admin configuration for Field Monitoring
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    FieldVisitReport,
    VisitingTeamMember,
    PersonMet,
    ServiceProvided,
    Challenge,
    BestPractice,
    CollaboratingPartner,
    FieldVisitAttachment,
)


class VisitingTeamMemberInline(admin.TabularInline):
    """Inline admin for visiting team members"""
    model = VisitingTeamMember
    extra = 1
    fields = ('name', 'title_organization', 'telephone', 'email')


class PersonMetInline(admin.TabularInline):
    """Inline admin for persons met"""
    model = PersonMet
    extra = 1
    fields = ('name', 'title')


class ServiceProvidedInline(admin.TabularInline):
    """Inline admin for services provided"""
    model = ServiceProvided
    extra = 1
    fields = ('service_name', 'indicator')


class ChallengeInline(admin.TabularInline):
    """Inline admin for challenges"""
    model = Challenge
    extra = 1
    fields = ('challenge_description', 'priority')


class BestPracticeInline(admin.TabularInline):
    """Inline admin for best practices"""
    model = BestPractice
    extra = 1
    fields = ('practice_description', 'replicable')


class CollaboratingPartnerInline(admin.TabularInline):
    """Inline admin for collaborating partners"""
    model = CollaboratingPartner
    extra = 1
    fields = ('partner_name', 'contact_person', 'contact_details')


class FieldVisitAttachmentInline(admin.TabularInline):
    """Inline admin for attachments"""
    model = FieldVisitAttachment
    extra = 1
    fields = ('document_type', 'file', 'description', 'uploaded_at')
    readonly_fields = ('uploaded_at',)


@admin.register(FieldVisitReport)
class FieldVisitReportAdmin(admin.ModelAdmin):
    """Admin interface for field visit reports"""
    
    list_display = (
        'report_code',
        'organization_name',
        'county',
        'visit_date',
        'status_badge',
        'report_compiled_by',
    )
    list_filter = (
        'status',
        'county',
        'visit_date',
        'created_at',
    )
    search_fields = (
        'report_code',
        'organization_name',
        'location_details',
    )
    readonly_fields = (
        'report_code',
        'created_at',
        'updated_at',
    )
    
    fieldsets = (
        ('Report Information', {
            'fields': (
                'report_code',
                'status',
                'report_date',
            ),
        }),
        ('Visit Details', {
            'fields': (
                'organization_name',
                'county',
                'location_details',
                'visit_date',
                'last_visit_date',
            ),
        }),
        ('Data Collection', {
            'fields': ('data_collection_methods',),
            'classes': ('collapse',),
        }),
        ('Personnel', {
            'fields': (
                'report_compiled_by',
                'report_submitted_by',
            ),
        }),
        ('Approval', {
            'fields': (
                'approved_by',
                'approved_at',
            ),
            'classes': ('collapse',),
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    inlines = [
        VisitingTeamMemberInline,
        PersonMetInline,
        ServiceProvidedInline,
        ChallengeInline,
        BestPracticeInline,
        CollaboratingPartnerInline,
        FieldVisitAttachmentInline,
    ]
    
    actions = ['mark_submitted', 'mark_reviewed', 'mark_approved']
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'draft': '#99ccff',
            'submitted': '#ffcc99',
            'reviewed': '#ccffcc',
            'approved': '#99ff99',
            'archived': '#cccccc',
        }
        color = colors.get(obj.status, '#ffffff')
        return format_html(
            '<span style="background-color: {}; padding: 5px 10px; border-radius: 3px; color: black;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = 'Status'
    
    def mark_submitted(self, request, queryset):
        """Bulk action to mark reports as submitted"""
        updated = queryset.update(status='submitted')
        self.message_user(request, f'{updated} reports marked as submitted')
    mark_submitted.short_description = "Mark selected as Submitted"
    
    def mark_reviewed(self, request, queryset):
        """Bulk action to mark reports as reviewed"""
        updated = queryset.update(status='reviewed')
        self.message_user(request, f'{updated} reports marked as reviewed')
    mark_reviewed.short_description = "Mark selected as Reviewed"
    
    def mark_approved(self, request, queryset):
        """Bulk action to mark reports as approved"""
        from django.utils import timezone
        for report in queryset:
            report.status = 'approved'
            report.approved_by = request.user
            report.approved_at = timezone.now()
            report.save()
        self.message_user(request, f'{queryset.count()} reports approved')
    mark_approved.short_description = "Approve selected reports"


@admin.register(VisitingTeamMember)
class VisitingTeamMemberAdmin(admin.ModelAdmin):
    """Admin for visiting team members"""
    list_display = ('name', 'title_organization', 'visit', 'telephone', 'email')
    list_filter = ('visit__visit_date', 'visit__county')
    search_fields = ('name', 'title_organization', 'email')


@admin.register(ServiceProvided)
class ServiceProvidedAdmin(admin.ModelAdmin):
    """Admin for services provided"""
    list_display = ('service_name', 'visit', 'indicator')
    list_filter = ('visit__visit_date', 'indicator')
    search_fields = ('service_name', 'findings', 'recommended_action')
    readonly_fields = ('visit',)


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    """Admin for challenges"""
    list_display = ('challenge_description', 'visit', 'priority', 'priority_badge')
    list_filter = ('priority', 'visit__visit_date', 'visit__county')
    search_fields = ('challenge_description', 'recommendation')
    
    def priority_badge(self, obj):
        """Display priority as colored badge"""
        colors = {
            'low': '#ccffcc',
            'medium': '#ffcc99',
            'high': '#ff9999',
            'critical': '#ff0000',
        }
        color = colors.get(obj.priority, '#ffffff')
        return format_html(
            '<span style="background-color: {}; padding: 5px 10px; border-radius: 3px; color: white;">{}</span>',
            color,
            obj.get_priority_display(),
        )
    priority_badge.short_description = 'Priority Level'


@admin.register(BestPractice)
class BestPracticeAdmin(admin.ModelAdmin):
    """Admin for best practices"""
    list_display = ('practice_description', 'visit', 'replicable', 'replicable_badge')
    list_filter = ('replicable', 'visit__visit_date', 'visit__county')
    search_fields = ('practice_description', 'lessons_learned')
    
    def replicable_badge(self, obj):
        """Display replicable status"""
        badge = '✓ Yes' if obj.replicable else '✗ No'
        color = '#ccffcc' if obj.replicable else '#ffcccc'
        return format_html(
            '<span style="background-color: {}; padding: 5px 10px; border-radius: 3px;">{}</span>',
            color,
            badge,
        )
    replicable_badge.short_description = 'Can Replicate'


@admin.register(CollaboratingPartner)
class CollaboratingPartnerAdmin(admin.ModelAdmin):
    """Admin for collaborating partners"""
    list_display = ('partner_name', 'visit', 'contact_person', 'contact_details')
    list_filter = ('visit__visit_date', 'visit__county')
    search_fields = ('partner_name', 'contact_person', 'contact_details')


@admin.register(FieldVisitAttachment)
class FieldVisitAttachmentAdmin(admin.ModelAdmin):
    """Admin for attachments"""
    list_display = ('description', 'visit', 'document_type', 'uploaded_at', 'file_link')
    list_filter = ('document_type', 'uploaded_at', 'visit__visit_date')
    search_fields = ('description', 'visit__organization_name')
    readonly_fields = ('uploaded_at', 'file_preview')
    
    def file_link(self, obj):
        """Link to download file"""
        if obj.file:
            return format_html(
                '<a href="{}" target="_blank">Download</a>',
                obj.file.url,
            )
        return '-'
    file_link.short_description = 'File'
    
    def file_preview(self, obj):
        """Preview of file"""
        if obj.file:
            return format_html(
                '<a href="{}" target="_blank">View File</a>',
                obj.file.url,
            )
        return 'No file attached'
    file_preview.short_description = 'File Preview'
