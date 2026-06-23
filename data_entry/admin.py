from django.contrib import admin
from .models import DataEntry

@admin.register(DataEntry)
class DataEntryAdmin(admin.ModelAdmin):
    list_display = ['county', 'quarter', 'indicator', 'value', 'status', 'submitted_at', 'approved_at']
    list_filter = ['county', 'quarter', 'status']
    search_fields = ['county__name', 'indicator__code', 'indicator__name']
    readonly_fields = ['submitted_at', 'approved_at', 'created_at', 'updated_at']
    ordering = ['-created_at']
    fieldsets = (
        ('Data Entry', {'fields': ('county', 'quarter', 'indicator', 'value')}),
        ('Status', {'fields': ('status', 'is_locked', 'notes')}),
        ('Submission Info', {'fields': ('submitted_by', 'submitted_at', 'approved_by', 'approved_at', 'rejection_reason')}),
        ('Target', {'fields': ('target_at_submission',)}),
    )
