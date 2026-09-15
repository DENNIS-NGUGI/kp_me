from django.contrib import admin
from django.db.models import Q
from django.utils import timezone

from .models import Activity, ActivityIndicator, ActivityYearData, Commitment, CommitmentAccessPolicy, CommitmentNarrativeReport, IcpdActualSubmission, IcpdExpenditureSubmission, IcpdSubmissionAudit, IndicatorYearData, Objective


class ObjectiveInline(admin.TabularInline):
	model = Objective
	extra = 0


class CommitmentAccessPolicyInline(admin.StackedInline):
	model = CommitmentAccessPolicy
	extra = 0
	max_num = 1
	filter_horizontal = ('allowed_roles', 'allowed_users')


@admin.register(Commitment)
class CommitmentAdmin(admin.ModelAdmin):
	list_display = ('title', 'is_active', 'sort_order')
	list_filter = ('is_active',)
	search_fields = ('title', 'description')
	ordering = ('sort_order', 'title')
	inlines = (CommitmentAccessPolicyInline, ObjectiveInline)


@admin.register(CommitmentAccessPolicy)
class CommitmentAccessPolicyAdmin(admin.ModelAdmin):
	list_display = ('commitment', 'is_restricted', 'updated_at')
	list_filter = ('is_restricted',)
	search_fields = ('commitment__title',)
	autocomplete_fields = ('commitment',)
	filter_horizontal = ('allowed_roles', 'allowed_users')
	readonly_fields = ('updated_at',)


@admin.register(Objective)
class ObjectiveAdmin(admin.ModelAdmin):
	list_display = ('title', 'commitment', 'sort_order')
	list_filter = ('commitment',)
	search_fields = ('title', 'description')
	ordering = ('commitment', 'sort_order', 'title')


class ActivityIndicatorInline(admin.TabularInline):
	model = ActivityIndicator
	extra = 0


class ActivityYearDataInline(admin.TabularInline):
	model = ActivityYearData
	extra = 0


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
	list_display = ('title', 'objective', 'timeline', 'responsible_organization_names', 'budget_amount')
	list_filter = ('objective__commitment',)
	search_fields = ('title', 'responsible_organizations__name')
	filter_horizontal = ('responsible_organizations',)
	ordering = ('objective', 'sort_order', 'id')
	inlines = (ActivityIndicatorInline, ActivityYearDataInline)

	@admin.display(description='Responsible organizations')
	def responsible_organization_names(self, obj):
		return ', '.join(obj.responsible_organizations.values_list('name', flat=True)) or '-'


class IndicatorYearDataInline(admin.TabularInline):
	model = IndicatorYearData
	extra = 0


@admin.register(ActivityIndicator)
class ActivityIndicatorAdmin(admin.ModelAdmin):
	list_display = ('code', 'name', 'activity', 'baseline_value', 'baseline_year')
	list_filter = ('activity__objective__commitment',)
	search_fields = ('code', 'name', 'activity__title')
	autocomplete_fields = ('activity',)
	readonly_fields = ('code',)
	inlines = (IndicatorYearDataInline,)


@admin.register(IndicatorYearData)
class IndicatorYearDataAdmin(admin.ModelAdmin):
	list_display = ('activity_indicator', 'financial_year', 'target_value', 'achievement_value', 'status')
	list_filter = ('financial_year', 'status')
	search_fields = ('activity_indicator__code', 'activity_indicator__name')
	autocomplete_fields = ('activity_indicator',)


@admin.register(ActivityYearData)
class ActivityYearDataAdmin(admin.ModelAdmin):
	list_display = ('activity', 'financial_year', 'expenditure_amount')
	list_filter = ('financial_year', 'activity__objective__commitment')
	search_fields = ('activity__title',)
	autocomplete_fields = ('activity',)


class ReportAdmin(admin.ModelAdmin):
	"""Allow corrections before review while keeping submitted reports locked."""
	commitment_lookup = None

	def get_queryset(self, request):
		queryset = super().get_queryset(request)
		if request.user.is_superuser or not self.commitment_lookup:
			return queryset
		return queryset.filter(
			Q(**{f'{self.commitment_lookup}__access_policy__isnull': True})
			| Q(**{f'{self.commitment_lookup}__access_policy__is_restricted': False})
			| Q(**{f'{self.commitment_lookup}__access_policy__allowed_users': request.user})
			| Q(**{f'{self.commitment_lookup}__access_policy__allowed_roles': request.user.role_id if request.user.role_id else None}),
		).distinct()

	def has_add_permission(self, request):
		return False

	def has_change_permission(self, request, obj=None):
		if not super().has_change_permission(request, obj):
			return False
		if request.user.is_superuser:
			return True
		return obj is None or obj.workflow_status in ('draft', 'returned')

	def has_delete_permission(self, request, obj=None):
		return False

	def can_approve_reports(self, request):
		return request.user.is_superuser or request.user.has_permission('can_approve_data')

	def get_actions(self, request):
		actions = super().get_actions(request)
		if not self.can_approve_reports(request):
			actions.pop('approve_selected_reports', None)
		return actions


@admin.register(IcpdActualSubmission)
class IcpdActualSubmissionAdmin(ReportAdmin):
	commitment_lookup = 'indicator_year_data__activity_indicator__activity__objective__commitment'
	list_display = ('indicator_year_data', 'activity_report', 'submitted_by', 'achievement_value', 'status', 'workflow_status', 'submitted_at', 'approved_by')
	list_filter = ('workflow_status', 'status', 'indicator_year_data__financial_year')
	search_fields = ('indicator_year_data__activity_indicator__code', 'indicator_year_data__activity_indicator__name', 'activity_report__activity__title', 'submitted_by__username', 'organization')
	list_select_related = ('indicator_year_data__activity_indicator__activity', 'activity_report', 'submitted_by', 'approved_by')
	readonly_fields = ('indicator_year_data', 'activity_report', 'submitted_by', 'organization', 'status', 'workflow_status', 'submitted_at', 'approved_by', 'approved_at', 'returned_by', 'returned_at', 'return_reason', 'created_at', 'updated_at')
	date_hierarchy = 'submitted_at'
	actions = ('approve_selected_reports',)

	def save_model(self, request, obj, form, change):
		obj.status = obj.status_for_achievement(
			obj.indicator_year_data.target_value,
			obj.achievement_value,
		)
		super().save_model(request, obj, form, change)

	@admin.action(description='Approve selected actual submissions')
	def approve_selected_reports(self, request, queryset):
		if not self.can_approve_reports(request):
			self.message_user(request, 'You do not have permission to approve ICPD reports.', level='error')
			return
		eligible = queryset.filter(workflow_status='submitted').exclude(submitted_by=request.user)
		updated = eligible.update(workflow_status='approved', approved_by=request.user, approved_at=timezone.now())
		self.message_user(request, f'{updated} actual submission(s) approved.')


@admin.register(IcpdExpenditureSubmission)
class IcpdExpenditureSubmissionAdmin(ReportAdmin):
	commitment_lookup = 'activity__objective__commitment'
	list_display = ('activity', 'financial_year', 'submitted_by', 'expenditure_amount', 'workflow_status', 'submitted_at', 'approved_by')
	list_filter = ('workflow_status', 'financial_year', 'activity__objective__commitment')
	search_fields = ('activity__title', 'submitted_by__username', 'organization')
	list_select_related = ('activity__objective__commitment', 'submitted_by', 'approved_by')
	readonly_fields = ('activity', 'financial_year', 'submitted_by', 'organization', 'workflow_status', 'submitted_at', 'approved_by', 'approved_at', 'returned_by', 'returned_at', 'return_reason', 'created_at', 'updated_at')
	date_hierarchy = 'submitted_at'
	actions = ('approve_selected_reports',)

	@admin.action(description='Approve selected expenditure submissions')
	def approve_selected_reports(self, request, queryset):
		if not self.can_approve_reports(request):
			self.message_user(request, 'You do not have permission to approve ICPD reports.', level='error')
			return
		eligible = queryset.filter(workflow_status='submitted').exclude(submitted_by=request.user)
		updated = eligible.update(workflow_status='approved', approved_by=request.user, approved_at=timezone.now())
		self.message_user(request, f'{updated} expenditure submission(s) approved.')


@admin.register(CommitmentNarrativeReport)
class CommitmentNarrativeReportAdmin(ReportAdmin):
	commitment_lookup = 'commitment'
	list_display = ('commitment', 'financial_year', 'author', 'workflow_status', 'submitted_at', 'approved_by', 'approved_at')
	list_filter = ('workflow_status', 'financial_year', 'commitment')
	search_fields = ('commitment__title', 'author__username', 'author__first_name', 'author__last_name')
	list_select_related = ('commitment', 'author', 'approved_by')
	readonly_fields = ('commitment', 'author', 'financial_year', 'workflow_status', 'submitted_at', 'approved_by', 'approved_at', 'created_at', 'updated_at')
	date_hierarchy = 'submitted_at'
	actions = ('approve_selected_reports',)

	@admin.action(description='Approve selected commitment narratives')
	def approve_selected_reports(self, request, queryset):
		if not self.can_approve_reports(request):
			self.message_user(request, 'You do not have permission to approve ICPD reports.', level='error')
			return
		eligible = queryset.filter(workflow_status='submitted').exclude(author=request.user)
		updated = eligible.update(workflow_status='approved', approved_by=request.user, approved_at=timezone.now())
		self.message_user(request, f'{updated} commitment narrative(s) approved.')


@admin.register(IcpdSubmissionAudit)
class IcpdSubmissionAuditAdmin(ReportAdmin):
	list_display = ('submission_type', 'submission_id', 'action', 'actor', 'created_at')
	list_filter = ('submission_type', 'action')
	search_fields = ('actor__username',)
	list_select_related = ('actor',)
	readonly_fields = ('submission_type', 'submission_id', 'action', 'actor', 'old_value', 'new_value', 'created_at')
	date_hierarchy = 'created_at'

	def has_change_permission(self, request, obj=None):
		return admin.ModelAdmin.has_change_permission(self, request, obj) and request.method in ('GET', 'HEAD')
