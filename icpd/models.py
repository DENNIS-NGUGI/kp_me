from django.db import models
from django.db.models import Sum
from django.utils import timezone


FINANCIAL_YEAR_CHOICES = [
	('2019/20', '2019/20'),
	('2020/21', '2020/21'),
	('2021/22', '2021/22'),
	('2022/23', '2022/23'),
	('2023/24', '2023/24'),
	('2024/25', '2024/25'),
	('2025/26', '2025/26'),
	('2026/27', '2026/27'),
	('2027/28', '2027/28'),
	('2028/29', '2028/29'),
	('2029/30', '2029/30'),
]


class Commitment(models.Model):
	"""A national ICPD commitment containing one or more objectives."""

	title = models.CharField(max_length=500)
	description = models.TextField(blank=True)
	sort_order = models.PositiveIntegerField(default=0)
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ['sort_order', 'title']
		constraints = [
			models.UniqueConstraint(
				fields=['title'],
				name='unique_icpd_commitment_title',
			),
		]

	def __str__(self):
		return self.title


class CommitmentAccessPolicy(models.Model):
	"""Optional role and user assignments for an ICPD commitment."""

	commitment = models.OneToOneField(
		Commitment,
		on_delete=models.CASCADE,
		related_name='access_policy',
	)
	is_restricted = models.BooleanField(default=False)
	allowed_roles = models.ManyToManyField(
		'users.Role',
		blank=True,
		related_name='icpd_commitment_access_policies',
	)
	allowed_users = models.ManyToManyField(
		'users.User',
		blank=True,
		related_name='icpd_commitment_access_policies',
	)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		verbose_name = 'Commitment access policy'
		verbose_name_plural = 'Commitment access policies'

	def __str__(self):
		return f'Access policy: {self.commitment}'


class CommitmentNarrativeReport(models.Model):
	"""One user's narrative for a commitment and financial year."""

	commitment = models.ForeignKey(
		Commitment,
		on_delete=models.CASCADE,
		related_name='narrative_reports',
	)
	author = models.ForeignKey(
		'users.User',
		on_delete=models.CASCADE,
		related_name='icpd_narrative_reports',
	)
	financial_year = models.CharField(max_length=7, choices=FINANCIAL_YEAR_CHOICES, default='2025/26')
	introduction = models.TextField(blank=True)
	other_actor_contributions = models.TextField(blank=True)
	facilitating_factors = models.TextField(blank=True)
	challenges = models.TextField(blank=True)
	opportunities = models.TextField(blank=True)
	conclusion_and_recommendations = models.TextField(blank=True)
	implementation_status = models.TextField()
	takeaways_and_priority_next_steps = models.TextField()
	abbreviations = models.TextField(blank=True)
	executive_summary = models.TextField()
	references = models.TextField(blank=True)
	workflow_status = models.CharField(max_length=20, choices=[
		('draft', 'Draft'),
		('submitted', 'Submitted for review'),
		('approved', 'Approved'),
	], default='submitted')
	submitted_at = models.DateTimeField(null=True, blank=True)
	approved_by = models.ForeignKey(
		'users.User', on_delete=models.SET_NULL, null=True, blank=True,
		related_name='approved_icpd_narrative_reports',
	)
	approved_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['commitment', 'financial_year', 'author']
		constraints = [
			models.UniqueConstraint(
				fields=['commitment', 'financial_year'],
				name='unique_icpd_narrative_report_per_financial_year',
			),
		]
		verbose_name = 'Commitment narrative report'
		verbose_name_plural = 'Commitment narrative reports'

	def __str__(self):
		return f'{self.commitment} - {self.financial_year} - {self.author}'

	def submit(self):
		self.workflow_status = 'submitted'
		self.submitted_at = timezone.now()
		self.approved_by = None
		self.approved_at = None


class Objective(models.Model):
	"""A measurable objective under an ICPD commitment."""

	commitment = models.ForeignKey(
		Commitment,
		on_delete=models.CASCADE,
		related_name='objectives',
	)
	title = models.CharField(max_length=500)
	description = models.TextField(blank=True)
	sort_order = models.PositiveIntegerField(default=0)

	class Meta:
		ordering = ['commitment', 'sort_order', 'title']
		constraints = [
			models.UniqueConstraint(
				fields=['commitment', 'title'],
				name='unique_icpd_objective_per_commitment',
			),
		]

	def __str__(self):
		return self.title

	@property
	def responsible_organization_names(self):
		return ', '.join(self.responsible_organizations.values_list('name', flat=True))


class Activity(models.Model):
	"""A key action or activity delivered in support of an objective."""

	objective = models.ForeignKey(
		Objective,
		on_delete=models.CASCADE,
		related_name='activities',
	)
	title = models.TextField()
	timeline = models.CharField(max_length=255, blank=True)
	responsibility = models.CharField(max_length=255, blank=True)
	responsible_organizations = models.ManyToManyField(
		'users.Organization',
		blank=True,
		related_name='responsible_activities',
	)
	budget_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
	budget_currency = models.CharField(max_length=3, default='KES')
	cumulative_target_is_static = models.BooleanField(
		default=False,
		help_text='Use the latest annual target as the cumulative target instead of adding targets across years.',
	)
	remarks = models.TextField(blank=True)
	sort_order = models.PositiveIntegerField(default=0)

	class Meta:
		ordering = ['objective', 'sort_order', 'id']
		constraints = [
			models.UniqueConstraint(
				fields=['objective', 'title'],
				name='unique_icpd_activity_per_objective',
			),
		]

	def __str__(self):
		return self.title

	def approved_expenditure_for_year(self, financial_year):
		return self.expenditure_submissions.filter(
			financial_year=financial_year,
			workflow_status='approved',
		).aggregate(total=Sum('expenditure_amount'))['total']


class ActivityYearData(models.Model):
	"""Annual actual expenditure recorded once for an activity and financial year."""

	activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='yearly_expenditure')
	financial_year = models.CharField(max_length=7, choices=FINANCIAL_YEAR_CHOICES)
	expenditure_amount = models.DecimalField(
		max_digits=20,
		decimal_places=2,
		null=True,
		blank=True,
		help_text='Actual expenditure in KES millions for this financial year.',
	)
	remarks = models.TextField(blank=True)

	class Meta:
		ordering = ['financial_year']
		constraints = [
			models.UniqueConstraint(
				fields=['activity', 'financial_year'],
				name='unique_icpd_activity_financial_year',
			),
		]

	def __str__(self):
		return f'{self.activity} ({self.financial_year})'


class IcpdActualSubmission(models.Model):
	"""One indicator achievement within a responsible organization's activity report."""

	STATUS_CHOICES = [
		('draft', 'Draft'),
		('submitted', 'Submitted for review'),
		('returned', 'Returned for correction'),
		('approved', 'Approved'),
	]

	indicator_year_data = models.ForeignKey(
		'IndicatorYearData', on_delete=models.CASCADE, related_name='actual_submissions',
	)
	activity_report = models.ForeignKey(
		'IcpdExpenditureSubmission', on_delete=models.CASCADE, related_name='actual_submissions',
	)
	submitted_by = models.ForeignKey(
		'users.User', on_delete=models.PROTECT, related_name='icpd_actual_submissions',
	)
	organization = models.CharField(max_length=200, blank=True)
	achievement_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
	status = models.CharField(
		max_length=20,
		choices=[
			('not_started', 'Not Started'),
			('on_track', 'On Track'),
			('at_risk', 'At Risk'),
			('achieved', 'Achieved'),
			('not_reported', 'Not Reported'),
		],
		default='not_reported',
	)
	remarks = models.TextField(blank=True)
	workflow_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
	submitted_at = models.DateTimeField(null=True, blank=True)
	approved_by = models.ForeignKey(
		'users.User', on_delete=models.SET_NULL, null=True, blank=True,
		related_name='approved_icpd_actual_submissions',
	)
	approved_at = models.DateTimeField(null=True, blank=True)
	returned_by = models.ForeignKey(
		'users.User', on_delete=models.SET_NULL, null=True, blank=True,
		related_name='returned_icpd_actual_submissions',
	)
	returned_at = models.DateTimeField(null=True, blank=True)
	return_reason = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['indicator_year_data', 'organization', 'submitted_by']
		constraints = [
			models.UniqueConstraint(
				fields=['indicator_year_data', 'activity_report'],
				name='unique_icpd_actual_submission_per_activity_report',
			),
		]

	def __str__(self):
		return f'{self.indicator_year_data} - {self.organization or self.submitted_by}'

	@staticmethod
	def status_for_achievement(target_value, achievement_value):
		if target_value is None or achievement_value is None or target_value <= 0:
			return 'not_reported'
		if achievement_value <= 0:
			return 'not_started'
		if achievement_value >= target_value:
			return 'achieved'
		if achievement_value / target_value >= 0.75:
			return 'on_track'
		return 'at_risk'

	def submit(self):
		self.workflow_status = 'submitted'
		self.submitted_at = timezone.now()
		self.approved_by = None
		self.approved_at = None
		self.returned_by = None
		self.returned_at = None
		self.return_reason = ''


class IcpdExpenditureSubmission(models.Model):
	"""The responsible organization's report and workflow lock for one activity year."""

	activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='expenditure_submissions')
	financial_year = models.CharField(max_length=7, choices=FINANCIAL_YEAR_CHOICES)
	submitted_by = models.ForeignKey(
		'users.User', on_delete=models.PROTECT, related_name='icpd_expenditure_submissions',
	)
	organization = models.CharField(max_length=200, blank=True)
	expenditure_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
	remarks = models.TextField(blank=True)
	workflow_status = models.CharField(max_length=20, choices=IcpdActualSubmission.STATUS_CHOICES, default='draft')
	submitted_at = models.DateTimeField(null=True, blank=True)
	approved_by = models.ForeignKey(
		'users.User', on_delete=models.SET_NULL, null=True, blank=True,
		related_name='approved_icpd_expenditure_submissions',
	)
	approved_at = models.DateTimeField(null=True, blank=True)
	returned_by = models.ForeignKey(
		'users.User', on_delete=models.SET_NULL, null=True, blank=True,
		related_name='returned_icpd_expenditure_submissions',
	)
	returned_at = models.DateTimeField(null=True, blank=True)
	return_reason = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['activity', 'financial_year']
		constraints = [
			models.UniqueConstraint(
				fields=['activity', 'financial_year'],
				name='unique_icpd_activity_report_per_financial_year',
			),
		]

	def __str__(self):
		return f'{self.activity} ({self.financial_year}) - {self.organization or self.submitted_by}'

	def submit(self):
		self.workflow_status = 'submitted'
		self.submitted_at = timezone.now()
		self.approved_by = None
		self.approved_at = None
		self.returned_by = None
		self.returned_at = None
		self.return_reason = ''


class IcpdSubmissionAudit(models.Model):
	"""Immutable history of ICPD actual and expenditure submission changes."""

	SUBMISSION_TYPE_CHOICES = [('actual', 'Actual'), ('expenditure', 'Expenditure')]
	ACTION_CHOICES = [('created', 'Created'), ('updated', 'Updated'), ('submitted', 'Submitted'), ('returned', 'Returned'), ('approved', 'Approved')]

	submission_type = models.CharField(max_length=20, choices=SUBMISSION_TYPE_CHOICES)
	submission_id = models.PositiveBigIntegerField()
	action = models.CharField(max_length=20, choices=ACTION_CHOICES)
	actor = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, related_name='icpd_submission_audit_events')
	old_value = models.JSONField(null=True, blank=True)
	new_value = models.JSONField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']
		indexes = [models.Index(fields=['submission_type', 'submission_id', '-created_at'])]

	def __str__(self):
		return f'{self.submission_type} {self.submission_id}: {self.action}'


class ActivityIndicator(models.Model):
	"""An ICPD-specific indicator assigned to one planned activity."""

	activity = models.ForeignKey(
		Activity,
		on_delete=models.CASCADE,
		related_name='activity_indicators',
	)
	code = models.CharField(max_length=50, blank=True, editable=False)
	name = models.CharField(max_length=500)
	baseline_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
	baseline_year = models.CharField(max_length=9, blank=True)
	notes = models.TextField(blank=True)

	class Meta:
		ordering = ['activity', 'code']
		constraints = [
			models.UniqueConstraint(
				fields=['activity', 'code'],
				name='unique_icpd_indicator_per_activity',
			),
			models.UniqueConstraint(
				fields=['activity', 'name'],
				name='unique_icpd_indicator_name_per_activity',
			),
		]

	def __str__(self):
		return f'{self.activity} - {self.code}: {self.name}'

	def save(self, *args, **kwargs):
		if self.code:
			return super().save(*args, **kwargs)
		super().save(*args, **kwargs)
		self.code = f'ICPD-{self.pk:04d}'
		type(self).objects.filter(pk=self.pk).update(code=self.code)

	@property
	def cumulative_target_value(self):
		if self.activity.cumulative_target_is_static:
			latest_year_data = self.yearly_data.order_by('-financial_year').first()
			return latest_year_data.target_value if latest_year_data else None
		return self.yearly_data.aggregate(total=Sum('target_value'))['total']

	@property
	def cumulative_achievement_value(self):
		return self.yearly_data.aggregate(total=Sum('achievement_value'))['total']


class IndicatorYearData(models.Model):
	"""One target and achievement for an activity indicator in a financial year."""

	FINANCIAL_YEAR_CHOICES = FINANCIAL_YEAR_CHOICES
	STATUS_CHOICES = [
		('not_started', 'Not Started'),
		('on_track', 'On Track'),
		('at_risk', 'At Risk'),
		('achieved', 'Achieved'),
		('not_reported', 'Not Reported'),
	]

	activity_indicator = models.ForeignKey(
		ActivityIndicator,
		on_delete=models.CASCADE,
		related_name='yearly_data',
	)
	financial_year = models.CharField(max_length=7, choices=FINANCIAL_YEAR_CHOICES)
	target_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
	achievement_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_reported')
	remarks = models.TextField(blank=True)

	class Meta:
		ordering = ['financial_year']
		constraints = [
			models.UniqueConstraint(
				fields=['activity_indicator', 'financial_year'],
				name='unique_icpd_indicator_financial_year',
			),
		]

	def __str__(self):
		return f'{self.activity_indicator.code} ({self.financial_year})'

	@property
	def approved_achievement_value(self):
		return self.actual_submissions.filter(workflow_status='approved').aggregate(
			total=Sum('achievement_value'),
		)['total']
