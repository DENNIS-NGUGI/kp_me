from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, AuditLog, Role

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'is_system', 'is_active', 'user_count']
    list_filter = ['is_system', 'is_active']
    search_fields = ['name', 'description']
    filter_horizontal = ['permissions']
    
    def user_count(self, obj):
        return obj.users.count()
    user_count.short_description = 'Users'

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'role', 'county', 'organization', 'is_active']
    list_filter = ['role', 'county', 'is_active', 'is_verified']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {
            'fields': ('role', 'county', 'organization', 'phone_number', 'is_verified', 'approved_by', 'approved_at')
        }),
    )

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'model_name', 'timestamp']
    list_filter = ['action', 'model_name']
    search_fields = ['user__username', 'object_repr']
    readonly_fields = ['user', 'action', 'model_name', 'object_id', 'object_repr', 'changes', 'ip_address', 'user_agent', 'timestamp']
    
    def has_add_permission(self, request):
        return False