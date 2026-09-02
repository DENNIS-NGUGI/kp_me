from django.contrib import admin
from .models import SystemSetting

@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'setting_type', 'is_editable', 'updated_at']
    list_filter = ['setting_type', 'is_editable']
    search_fields = ['key', 'value', 'description']
    
    fieldsets = (
        ('Setting', {'fields': ('key', 'value', 'setting_type')}),
        ('Metadata', {'fields': ('description', 'is_editable', 'is_public')}),
        ('Audit', {'fields': ('updated_by', 'updated_at', 'created_at')}),
    )
    readonly_fields = ['updated_at', 'created_at']