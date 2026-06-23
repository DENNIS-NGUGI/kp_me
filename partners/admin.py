from django.contrib import admin
from .models import Partner, Project, ProjectMilestone, ProjectReport

@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'partner_type', 'contact_person', 'status', 'get_project_count']
    list_filter = ['partner_type', 'status']
    search_fields = ['name', 'code', 'contact_person', 'contact_email']
    filter_horizontal = ['counties', 'users']
    
    fieldsets = (
        ('Basic Information', {'fields': ('code', 'name', 'partner_type', 'description')}),
        ('Contact Information', {'fields': ('contact_person', 'contact_email', 'contact_phone', 'address', 'website')}),
        ('Location & Status', {'fields': ('counties', 'status')}),
        ('Users', {'fields': ('users',)}),
        ('Audit', {'fields': ('created_by', 'created_at', 'updated_at')}),
    )
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'partner', 'status', 'start_date', 'end_date', 'budget', 'get_progress']
    list_filter = ['status', 'partner', 'is_active']
    search_fields = ['code', 'name', 'partner__name']
    filter_horizontal = ['indicators', 'counties']
    
    fieldsets = (
        ('Basic Information', {'fields': ('code', 'name', 'partner', 'description')}),
        ('Timeline', {'fields': ('start_date', 'end_date', 'actual_end_date')}),
        ('Budget', {'fields': ('budget', 'expenditure')}),
        ('Links', {'fields': ('indicators', 'counties')}),
        ('Contact', {'fields': ('project_lead', 'project_email', 'project_phone')}),
        ('Status', {'fields': ('status', 'is_active')}),
        ('Audit', {'fields': ('created_by', 'created_at', 'updated_at')}),
    )
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ProjectMilestone)
class ProjectMilestoneAdmin(admin.ModelAdmin):
    list_display = ['project', 'name', 'due_date', 'is_completed', 'completed_date']
    list_filter = ['is_completed', 'project']
    search_fields = ['name', 'project__name']


@admin.register(ProjectReport)
class ProjectReportAdmin(admin.ModelAdmin):
    list_display = ['project', 'title', 'report_date', 'created_by']
    list_filter = ['project', 'report_date']
    search_fields = ['title', 'project__name']
