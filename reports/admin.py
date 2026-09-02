from django.contrib import admin
from .models import ReportAccessPolicy


@admin.register(ReportAccessPolicy)
class ReportAccessPolicyAdmin(admin.ModelAdmin):
	list_display = ['report_key', 'is_restricted', 'updated_at']
	list_filter = ['is_restricted']
	search_fields = ['report_key']
	filter_horizontal = ['allowed_roles', 'allowed_users']
