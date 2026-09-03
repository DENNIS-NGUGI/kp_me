from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from users.decorators import permission_required

from .models import Activity, ActivityIndicator, ActivityYearData, Commitment, CommitmentAccessPolicy, CommitmentNarrativeReport, FINANCIAL_YEAR_CHOICES, IndicatorYearData, Objective
from users.models import Role, User
from .forms import (
	ActivityForm,
	ActivityIndicatorForm,
	ActivityYearActualsForm,
	ActivityYearDataForm,
	CommitmentForm,
	CommitmentNarrativeReportForm,
	IndicatorYearActualsForm,
	IndicatorYearDataForm,
	ObjectiveForm,
)


def _commitment_detail_url(instance):
	if isinstance(instance, Commitment):
		return 'icpd:commitment_detail', instance.pk
	if isinstance(instance, Objective):
		return 'icpd:commitment_detail', instance.commitment_id
	if isinstance(instance, Activity):
		return 'icpd:commitment_detail', instance.objective.commitment_id
	if isinstance(instance, ActivityIndicator):
		return 'icpd:commitment_detail', instance.activity.objective.commitment_id
	if isinstance(instance, ActivityYearData):
		return 'icpd:commitment_detail', instance.activity.objective.commitment_id
	return 'icpd:commitment_detail', instance.activity_indicator.activity.objective.commitment_id


def _is_icpd_admin(user):
	return user.is_superuser or user.is_admin_user


def _require_icpd_admin(request):
	if _is_icpd_admin(request.user):
		return True
	messages.error(request, 'Only ICPD administrators can change preconfigured planning data.')
	return False


def _user_can_access_commitment(user, commitment):
	"""Return whether a user is assigned to a commitment's optional access policy."""
	if _is_icpd_admin(user):
		return True
	policy = getattr(commitment, 'access_policy', None)
	if not policy or not policy.is_restricted:
		return True
	return (
		policy.allowed_users.filter(pk=user.pk).exists()
		or (user.role_id and policy.allowed_roles.filter(pk=user.role_id).exists())
	)


def _visible_commitments(user):
	commitments = Commitment.objects.filter(is_active=True)
	if _is_icpd_admin(user):
		return commitments
	return commitments.filter(
		Q(access_policy__isnull=True)
		| Q(access_policy__is_restricted=False)
		| Q(access_policy__allowed_users=user)
		| Q(access_policy__allowed_roles=user.role_id if user.role_id else None),
	).distinct()


def _rolling_financial_years(reporting_year):
	"""Return the reporting FY and six immediately preceding financial years."""
	start_year = int(reporting_year.split('/')[0])
	return [f'{year}/{str(year + 1)[-2:]}' for year in range(start_year - 6, start_year + 1)]


def _commitment_trend_rows(commitment, reporting_year):
	financial_years = _rolling_financial_years(reporting_year)[-5:]
	year_data = IndicatorYearData.objects.filter(
		activity_indicator__activity__objective__commitment=commitment,
		financial_year__in=financial_years,
	).select_related('activity_indicator').order_by('activity_indicator__code', 'financial_year')
	by_indicator = {}
	for item in year_data:
		by_indicator.setdefault(item.activity_indicator.code, {
			'indicator': item.activity_indicator.name,
			'values': {},
		})['values'][item.financial_year] = item
	return financial_years, by_indicator


def _commitment_trend_display_rows(commitment, reporting_year):
	financial_years, indicators = _commitment_trend_rows(commitment, reporting_year)
	return financial_years, [
		{
			'code': code,
			'indicator': data['indicator'],
			'targets': [data['values'].get(year).target_value if data['values'].get(year) else '-' for year in financial_years],
			'achievements': [data['values'].get(year).achievement_value if data['values'].get(year) else '-' for year in financial_years],
		}
		for code, data in indicators.items()
	]


def _narrative_has_content(narrative):
	return narrative and any((
		narrative.introduction,
		narrative.executive_summary,
		narrative.abbreviations,
		narrative.other_actor_contributions,
		narrative.facilitating_factors,
		narrative.challenges,
		narrative.opportunities,
		narrative.conclusion_and_recommendations,
		narrative.references,
	))


def _require_commitment_access(request, commitment):
	if _user_can_access_commitment(request.user, commitment):
		return True
	messages.error(request, 'You are not assigned to this ICPD commitment.')
	return False


def _instance_commitment(instance):
	if isinstance(instance, Commitment):
		return instance
	if isinstance(instance, Objective):
		return instance.commitment
	if isinstance(instance, Activity):
		return instance.objective.commitment
	if isinstance(instance, ActivityIndicator):
		return instance.activity.objective.commitment
	if isinstance(instance, ActivityYearData):
		return instance.activity.objective.commitment
	return instance.activity_indicator.activity.objective.commitment


def _form_view(request, form_class, title, instance=None, initial=None):
	if instance and not _require_commitment_access(request, _instance_commitment(instance)):
		return redirect('icpd:dashboard')
	form = form_class(request.POST or None, instance=instance, initial=initial)
	if request.method == 'POST' and form.is_valid():
		saved_instance = form.save()
		messages.success(request, f'{title} saved successfully.')
		view_name, commitment_id = _commitment_detail_url(saved_instance)
		return redirect(view_name, pk=commitment_id)
	return render(request, 'icpd/form.html', {
		'form': form,
		'title': title,
		'is_edit': instance is not None,
	})


def _delete_view(request, instance, title):
	if not _require_commitment_access(request, _instance_commitment(instance)):
		return redirect('icpd:dashboard')
	if request.method == 'POST':
		view_name, commitment_id = _commitment_detail_url(instance)
		instance.delete()
		messages.success(request, f'{title} deleted successfully.')
		return redirect(view_name, pk=commitment_id)
	return render(request, 'icpd/confirm_delete.html', {'object': instance, 'title': title})


@login_required
@permission_required('view_commitment')
def dashboard(request):
	"""Show the ICPD commitments and a high-level delivery summary."""
	commitments = _visible_commitments(request.user).annotate(
		objective_count=Count('objectives', distinct=True),
		activity_count=Count('objectives__activities', distinct=True),
		indicator_count=Count(
			'objectives__activities__activity_indicators',
			distinct=True,
		),
	)
	context = {
		'commitments': commitments,
		'commitment_count': commitments.count(),
		'activity_count': Activity.objects.filter(objective__commitment__in=commitments).count(),
		'indicator_count': ActivityIndicator.objects.filter(activity__objective__commitment__in=commitments).count(),
		'on_track_count': IndicatorYearData.objects.filter(activity_indicator__activity__objective__commitment__in=commitments, status='on_track').count(),
		'at_risk_count': IndicatorYearData.objects.filter(activity_indicator__activity__objective__commitment__in=commitments, status='at_risk').count(),
		'can_add_commitment': _is_icpd_admin(request.user) and request.user.has_permission('add_commitment'),
		'can_view_activity_indicators': request.user.has_permission('view_activityindicator'),
		'can_manage_access': _is_icpd_admin(request.user) and request.user.has_permission('change_commitment'),
	}
	return render(request, 'icpd/dashboard.html', context)


@login_required
@permission_required('view_commitment')
def commitment_detail(request, pk):
	"""Display all objectives, activities, measures, and annual data for a commitment."""
	yearly_data = Prefetch(
		'yearly_data',
		queryset=IndicatorYearData.objects.order_by('financial_year'),
	)
	activity_indicators = Prefetch(
		'activity_indicators',
		queryset=ActivityIndicator.objects.prefetch_related(yearly_data),
	)
	activity_expenditure = Prefetch('yearly_expenditure', queryset=ActivityYearData.objects.order_by('financial_year'))
	commitment = get_object_or_404(
		Commitment.objects.prefetch_related(
		Prefetch('objectives__activities', queryset=Activity.objects.prefetch_related(activity_indicators, activity_expenditure)),
		),
		pk=pk,
	)
	if not _require_commitment_access(request, commitment):
		return redirect('icpd:dashboard')
	permissions = {
		'can_change_commitment': request.user.has_permission('change_commitment'),
		'can_delete_commitment': request.user.has_permission('delete_commitment'),
		'can_add_objective': request.user.has_permission('add_objective'),
		'can_change_objective': request.user.has_permission('change_objective'),
		'can_delete_objective': request.user.has_permission('delete_objective'),
		'can_add_activity': request.user.has_permission('add_activity'),
		'can_change_activity': request.user.has_permission('change_activity'),
		'can_delete_activity': request.user.has_permission('delete_activity'),
		'can_add_activity_indicator': request.user.has_permission('add_activityindicator'),
		'can_change_activity_indicator': request.user.has_permission('change_activityindicator'),
		'can_delete_activity_indicator': request.user.has_permission('delete_activityindicator'),
		'can_add_year_data': request.user.has_permission('add_indicatoryeardata'),
		'can_change_year_data': request.user.has_permission('change_indicatoryeardata'),
		'can_delete_year_data': request.user.has_permission('delete_indicatoryeardata'),
		'can_add_activity_year_data': request.user.has_permission('add_activityyeardata'),
		'can_change_activity_year_data': request.user.has_permission('change_activityyeardata'),
	}
	return render(request, 'icpd/commitment_detail.html', {
		'commitment': commitment,
		'is_icpd_admin': _is_icpd_admin(request.user),
		**permissions,
	})


@login_required
@permission_required('view_activityindicator')
def activity_indicator_list(request):
	"""Manage the ICPD-specific indicators assigned to planned activities."""
	indicators = ActivityIndicator.objects.select_related(
		'activity__objective__commitment',
	).prefetch_related('yearly_data')
	commitment_id = request.GET.get('commitment')
	objective_id = request.GET.get('objective')
	activity_id = request.GET.get('activity')
	if commitment_id:
		indicators = indicators.filter(activity__objective__commitment_id=commitment_id)
	if objective_id:
		indicators = indicators.filter(activity__objective_id=objective_id)
	if activity_id:
		indicators = indicators.filter(activity_id=activity_id)
	indicators = indicators.filter(activity__objective__commitment__in=_visible_commitments(request.user))
	paginator = Paginator(indicators, 25)
	page_obj = paginator.get_page(request.GET.get('page'))
	return render(request, 'icpd/activity_indicator_list.html', {
		'page_obj': page_obj,
		'activity_indicators': page_obj.object_list,
		'commitments': _visible_commitments(request.user),
		'objectives': Objective.objects.filter(commitment__in=_visible_commitments(request.user)).select_related('commitment'),
		'activities': Activity.objects.filter(objective__commitment__in=_visible_commitments(request.user)).select_related('objective__commitment'),
		'selected_commitment': commitment_id,
		'selected_objective': objective_id,
		'selected_activity': activity_id,
		'is_icpd_admin': _is_icpd_admin(request.user),
	})


@login_required
@permission_required('view_commitment')
def report_entry(request):
	"""Capture only annual ICPD actuals against an administrator-configured plan."""
	tab = request.GET.get('tab') or request.POST.get('tab') or 'actuals'
	commitment_id = request.GET.get('commitment') or request.POST.get('commitment')
	objective_id = request.GET.get('objective') or request.POST.get('objective')
	activity_id = request.GET.get('activity') or request.POST.get('activity')
	activity_indicator_id = request.GET.get('activity_indicator') or request.POST.get('activity_indicator')
	financial_year = request.GET.get('financial_year') or request.POST.get('financial_year')

	commitments = _visible_commitments(request.user)
	if tab == 'narrative':
		financial_year = request.GET.get('financial_year') or request.POST.get('financial_year') or '2025/26'
		valid_financial_years = {value for value, _ in FINANCIAL_YEAR_CHOICES}
		if financial_year not in valid_financial_years:
			financial_year = '2025/26'
		selected_commitment = commitments.filter(pk=commitment_id).first() if commitment_id else None
		narrative_report = None
		if selected_commitment:
			narrative_report = CommitmentNarrativeReport.objects.filter(
				commitment=selected_commitment,
				author=request.user,
				financial_year=financial_year,
			).first()
		if request.method == 'POST' and selected_commitment:
			form = CommitmentNarrativeReportForm(request.POST, instance=narrative_report)
			if form.is_valid():
				narrative = form.save(commit=False)
				narrative.commitment = selected_commitment
				narrative.author = request.user
				narrative.financial_year = financial_year
				narrative.save()
				messages.success(request, 'Commitment narrative report saved successfully.')
				return redirect(f'{request.path}?tab=narrative&commitment={selected_commitment.pk}&financial_year={financial_year}')
		else:
			form = CommitmentNarrativeReportForm(instance=narrative_report) if selected_commitment else None
		trend_years, trend_rows = _commitment_trend_display_rows(selected_commitment, financial_year) if selected_commitment else ([], [])
		saved_narratives = CommitmentNarrativeReport.objects.filter(
			commitment=selected_commitment,
			financial_year=financial_year,
		).select_related('author') if selected_commitment else CommitmentNarrativeReport.objects.none()
		if not _is_icpd_admin(request.user):
			saved_narratives = saved_narratives.filter(author=request.user)
		saved_narratives = [item for item in saved_narratives if _narrative_has_content(item)]
		return render(request, 'icpd/narrative_report.html', {
			'commitments': commitments,
			'selected_commitment': selected_commitment,
			'financial_year': financial_year,
			'financial_year_choices': FINANCIAL_YEAR_CHOICES,
			'form': form,
			'has_saved_narrative': _narrative_has_content(narrative_report),
			'saved_narratives': saved_narratives,
			'planned_objectives': Objective.objects.filter(commitment=selected_commitment) if selected_commitment else Objective.objects.none(),
			'planned_actions': Activity.objects.filter(
				objective__commitment=selected_commitment,
			).select_related('objective') if selected_commitment else Activity.objects.none(),
			'trend_years': trend_years,
			'trend_rows': trend_rows,
		})
	objectives = Objective.objects.filter(commitment_id=commitment_id) if commitment_id else Objective.objects.none()
	activities = Activity.objects.filter(objective_id=objective_id) if objective_id else Activity.objects.none()
	activity_indicators = ActivityIndicator.objects.filter(activity_id=activity_id) if activity_id else ActivityIndicator.objects.none()
	if activity_id and not Activity.objects.filter(
		pk=activity_id,
		objective_id=objective_id,
		objective__commitment_id=commitment_id,
	).exists():
		messages.error(request, 'Select an activity that belongs to the selected objective and commitment.')
		return redirect('icpd:report_entry')
	if commitment_id and not commitments.filter(pk=commitment_id).exists():
		messages.error(request, 'You are not assigned to the selected ICPD commitment.')
		return redirect('icpd:report_entry')
	year_data = None
	expenditure_data = None
	financial_years = []
	if activity_indicator_id:
		financial_years = list(IndicatorYearData.objects.filter(
			activity_indicator_id=activity_indicator_id,
		).values_list('financial_year', 'financial_year'))
	if activity_indicator_id and financial_year:
		year_data = get_object_or_404(
			IndicatorYearData.objects.select_related('activity_indicator__activity__objective__commitment'),
			activity_indicator_id=activity_indicator_id,
			financial_year=financial_year,
		)
		if str(year_data.activity_indicator.activity_id) != str(activity_id):
			messages.error(request, 'The selected activity indicator does not belong to this activity.')
			return redirect('icpd:report_entry')
		expenditure_data = ActivityYearData.objects.filter(
			activity_id=activity_id,
			financial_year=financial_year,
		).first()

	if request.method == 'POST' and year_data:
		can_save_expenditure = (
			request.user.has_permission('change_activityyeardata')
			if expenditure_data else request.user.has_permission('add_activityyeardata')
		)
		if not (request.user.has_permission('change_indicatoryeardata') and can_save_expenditure):
			messages.error(request, 'You do not have permission to submit ICPD actuals.')
			return redirect('icpd:report_entry')
		year_form = IndicatorYearActualsForm(request.POST, instance=year_data)
		expenditure_form = ActivityYearActualsForm(
			request.POST,
			instance=expenditure_data or ActivityYearData(
				activity_id=activity_id,
				financial_year=financial_year,
			),
			prefix='expenditure',
		)
		if year_form.is_valid() and expenditure_form.is_valid():
			year_form.save()
			expenditure_form.save()
			messages.success(request, 'ICPD achievement, status, expenditure, and remarks saved successfully.')
			return redirect(f'{request.path}?commitment={commitment_id}&objective={objective_id}&activity={activity_id}&activity_indicator={activity_indicator_id}&financial_year={financial_year}')
	else:
		year_form = IndicatorYearActualsForm(instance=year_data) if year_data else None
		expenditure_form = ActivityYearActualsForm(
			instance=expenditure_data or ActivityYearData(
				activity_id=activity_id,
				financial_year=financial_year,
			),
			prefix='expenditure',
		) if year_data else None

	return render(request, 'icpd/report_entry.html', {
		'commitments': commitments,
		'objectives': objectives,
		'activities': activities,
		'activity_indicators': activity_indicators,
		'financial_years': financial_years,
		'selected_commitment': commitment_id,
		'selected_objective': objective_id,
		'selected_activity': activity_id,
		'selected_activity_indicator': activity_indicator_id,
		'selected_financial_year': financial_year,
		'year_data': year_data,
		'expenditure_data': expenditure_data,
		'year_form': year_form,
		'expenditure_form': expenditure_form,
	})


@login_required
@permission_required('view_commitment')
def narrative_report_export(request):
	"""Export an ICPD commitment narrative and its rolling trend as Word."""
	from docx import Document
	from docx.shared import Pt

	commitment = get_object_or_404(Commitment, pk=request.GET.get('commitment'))
	financial_year = request.GET.get('financial_year', '2025/26')
	if financial_year not in {value for value, _ in FINANCIAL_YEAR_CHOICES}:
		return HttpResponse('Unknown reporting financial year.', status=400)
	if not _require_commitment_access(request, commitment):
		return redirect('icpd:report_entry')

	narratives = CommitmentNarrativeReport.objects.filter(
		commitment=commitment,
		financial_year=financial_year,
	).select_related('author')
	if not _is_icpd_admin(request.user):
		narratives = narratives.filter(author=request.user)
	selected_narrative_ids = request.GET.getlist('narrative')
	if not selected_narrative_ids:
		messages.error(request, 'Select at least one saved narrative to export.')
		return redirect(f'{request.path.rsplit("/export/", 1)[0]}/?tab=narrative&commitment={commitment.pk}&financial_year={financial_year}')
	narratives = narratives.filter(pk__in=selected_narrative_ids)
	if not any(_narrative_has_content(narrative) for narrative in narratives):
		messages.error(request, 'Save narrative content before exporting this report.')
		return redirect(f'{request.path.rsplit("/export/", 1)[0]}/?tab=narrative&commitment={commitment.pk}&financial_year={financial_year}')

	document = Document()
	styles = document.styles
	for style_name in ('Normal', 'Title', 'Heading 1', 'Heading 2'):
		style = styles[style_name]
		style.font.name = 'Tahoma'
		style.font.size = Pt(12)
		style.paragraph_format.line_spacing = 1.5

	document.add_heading('ICPD Commitment Implementation Report', level=0)
	document.add_paragraph(f'Commitment: {commitment.title}')
	document.add_paragraph(f'Reporting financial year: {financial_year}')
	financial_years, trend_indicators = _commitment_trend_rows(commitment, financial_year)
	planned_objectives = Objective.objects.filter(commitment=commitment)
	planned_actions = Activity.objects.filter(
		objective__commitment=commitment,
	).select_related('objective')
	for narrative in narratives:
		document.add_heading(narrative.author.get_full_name() or narrative.author.username, level=1)
		document.add_heading('a. Introduction (1-2 paragraphs)', level=2)
		document.add_paragraph(narrative.introduction or 'Not provided.')
		document.add_heading('State the objectives, and planned actions for the selected financial year', level=2)
		for objective in planned_objectives:
			document.add_paragraph(objective.title, style='List Bullet')
		for action in planned_actions:
			document.add_paragraph(action.title, style='List Bullet 2')
		document.add_heading('b. Executive summary', level=2)
		document.add_paragraph(narrative.executive_summary or 'Not provided.')
		document.add_heading('c. Abbreviations', level=2)
		document.add_paragraph(narrative.abbreviations or 'Not provided.')
		document.add_heading('d. Achievements (5 year period back from selected fy)', level=2)
		document.add_paragraph(f'Trend period: {financial_years[0]} to {financial_years[-1]}')
		table = document.add_table(rows=1, cols=2 + len(financial_years))
		table.style = 'Table Grid'
		for index, value in enumerate(['Indicator', 'Measure'] + financial_years):
			table.rows[0].cells[index].text = value
		for data in trend_indicators.values():
			for measure in ('Target', 'Achievement'):
				cells = table.add_row().cells
				cells[0].text = data['indicator']
				cells[1].text = measure
				for index, trend_year in enumerate(financial_years, start=2):
					item = data['values'].get(trend_year)
					cells[index].text = str(item.target_value if measure == 'Target' and item and item.target_value is not None else item.achievement_value if item and item.achievement_value is not None else '-')
		for heading, content in (
			('e. Contribution by other actors', narrative.other_actor_contributions),
			('f. Facilitating factors', narrative.facilitating_factors),
			('What challenges slowed progress?', narrative.challenges),
			('What opportunities to enhance implementation exist?', narrative.opportunities),
			('g. Conclusion and Recommendations', narrative.conclusion_and_recommendations),
			('h. References', narrative.references),
		):
			document.add_heading(heading, level=2)
			document.add_paragraph(content or 'Not provided.')

	response = HttpResponse(
		content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
	)
	response['Content-Disposition'] = f'attachment; filename="icpd_commitment_{commitment.pk}_{financial_year.replace("/", "_")}.docx"'
	document.save(response)
	return response


@login_required
@permission_required('add_commitment')
def commitment_create(request):
	if not _require_icpd_admin(request):
		return redirect('icpd:dashboard')
	return _form_view(request, CommitmentForm, 'Commitment')


@login_required
@permission_required('change_commitment')
def commitment_update(request, pk):
	if not _require_icpd_admin(request):
		return redirect('icpd:dashboard')
	return _form_view(request, CommitmentForm, 'Commitment', get_object_or_404(Commitment, pk=pk))


@login_required
@permission_required('change_commitment')
def commitment_access(request):
	"""Assign roles and users that may work on each ICPD commitment."""
	if not _require_icpd_admin(request):
		return redirect('icpd:dashboard')
	commitments = Commitment.objects.filter(is_active=True)
	if request.method == 'POST':
		roles = Role.objects.filter(is_active=True)
		users = User.objects.filter(is_active=True, is_verified=True)
		for commitment in commitments:
			policy, _ = CommitmentAccessPolicy.objects.get_or_create(commitment=commitment)
			policy.is_restricted = request.POST.get(f'restricted_{commitment.pk}') == 'on'
			policy.save()
			policy.allowed_roles.set(roles.filter(pk__in=request.POST.getlist(f'roles_{commitment.pk}')))
			policy.allowed_users.set(users.filter(pk__in=request.POST.getlist(f'users_{commitment.pk}')))
		messages.success(request, 'ICPD commitment access settings updated.')
		return redirect('icpd:commitment_access')
	policies = {
		policy.commitment_id: policy
		for policy in CommitmentAccessPolicy.objects.prefetch_related('allowed_roles', 'allowed_users')
	}
	settings = []
	for commitment in commitments:
		policy = policies.get(commitment.pk)
		settings.append({
			'commitment': commitment,
			'is_restricted': policy.is_restricted if policy else False,
			'allowed_role_ids': list(policy.allowed_roles.values_list('id', flat=True)) if policy else [],
			'allowed_user_ids': list(policy.allowed_users.values_list('id', flat=True)) if policy else [],
		})
	return render(request, 'icpd/access.html', {
		'commitment_access_settings': settings,
		'roles': Role.objects.filter(is_active=True).order_by('display_name', 'name'),
		'users': User.objects.filter(is_active=True, is_verified=True).select_related('role').order_by('username'),
	})


@login_required
@permission_required('delete_commitment')
def commitment_delete(request, pk):
	if not _require_icpd_admin(request):
		return redirect('icpd:dashboard')
	return _delete_view(request, get_object_or_404(Commitment, pk=pk), 'Commitment')


@login_required
@permission_required('add_objective')
def objective_create(request):
	if not _require_icpd_admin(request):
		return redirect('icpd:dashboard')
	commitment = get_object_or_404(Commitment, pk=request.GET.get('commitment') or request.POST.get('commitment'))
	if not _require_commitment_access(request, commitment):
		return redirect('icpd:dashboard')
	return _form_view(request, ObjectiveForm, 'Objective', initial={'commitment': commitment.pk})


@login_required
@permission_required('change_objective')
def objective_update(request, pk):
	if not _require_icpd_admin(request):
		return redirect('icpd:dashboard')
	return _form_view(request, ObjectiveForm, 'Objective', get_object_or_404(Objective, pk=pk))


@login_required
@permission_required('delete_objective')
def objective_delete(request, pk):
	if not _require_icpd_admin(request):
		return redirect('icpd:dashboard')
	return _delete_view(request, get_object_or_404(Objective, pk=pk), 'Objective')


@login_required
@permission_required('add_activity')
def activity_create(request):
	if not _require_icpd_admin(request):
		return redirect('icpd:dashboard')
	objective = get_object_or_404(Objective.objects.select_related('commitment'), pk=request.GET.get('objective') or request.POST.get('objective'))
	if not _require_commitment_access(request, objective.commitment):
		return redirect('icpd:dashboard')
	return _form_view(request, ActivityForm, 'Activity', initial={'objective': objective.pk})


@login_required
@permission_required('change_activity')
def activity_update(request, pk):
	if not _require_icpd_admin(request):
		return redirect('icpd:dashboard')
	return _form_view(request, ActivityForm, 'Activity', get_object_or_404(Activity, pk=pk))


@login_required
@permission_required('delete_activity')
def activity_delete(request, pk):
	if not _require_icpd_admin(request):
		return redirect('icpd:dashboard')
	return _delete_view(request, get_object_or_404(Activity, pk=pk), 'Activity')


@login_required
@permission_required('add_activityindicator')
def activity_indicator_create(request):
	if not _require_icpd_admin(request):
		return redirect('icpd:activity_indicator_list')
	activity_id = request.GET.get('activity') or request.POST.get('activity')
	if not activity_id:
		return _form_view(request, ActivityIndicatorForm, 'Activity Indicator')
	activity = get_object_or_404(Activity.objects.select_related('objective__commitment'), pk=activity_id)
	if not _require_commitment_access(request, activity.objective.commitment):
		return redirect('icpd:dashboard')
	return _form_view(request, ActivityIndicatorForm, 'Activity Indicator', initial={'activity': activity.pk})


@login_required
@permission_required('change_activityindicator')
def activity_indicator_update(request, pk):
	if not _require_icpd_admin(request):
		return redirect('icpd:activity_indicator_list')
	return _form_view(request, ActivityIndicatorForm, 'Activity Indicator', get_object_or_404(ActivityIndicator, pk=pk))


@login_required
@permission_required('delete_activityindicator')
def activity_indicator_delete(request, pk):
	if not _require_icpd_admin(request):
		return redirect('icpd:activity_indicator_list')
	return _delete_view(request, get_object_or_404(ActivityIndicator, pk=pk), 'Activity Indicator')


@login_required
@permission_required('add_indicatoryeardata')
def indicator_year_data_create(request):
	if not _require_icpd_admin(request):
		return redirect('icpd:dashboard')
	indicator = get_object_or_404(
		ActivityIndicator.objects.select_related('activity__objective__commitment'),
		pk=request.GET.get('activity_indicator') or request.POST.get('activity_indicator'),
	)
	if not _require_commitment_access(request, indicator.activity.objective.commitment):
		return redirect('icpd:dashboard')
	return _form_view(request, IndicatorYearDataForm, 'Annual Target', initial={'activity_indicator': indicator.pk})


@login_required
@permission_required('change_indicatoryeardata')
def indicator_year_data_update(request, pk):
	year_data = get_object_or_404(IndicatorYearData, pk=pk)
	form_class = IndicatorYearDataForm if _is_icpd_admin(request.user) else IndicatorYearActualsForm
	title = 'Annual Target' if _is_icpd_admin(request.user) else 'Yearly Indicator Actuals'
	return _form_view(request, form_class, title, year_data)


@login_required
@permission_required('delete_indicatoryeardata')
def indicator_year_data_delete(request, pk):
	if not _require_icpd_admin(request):
		return redirect('icpd:dashboard')
	return _delete_view(request, get_object_or_404(IndicatorYearData, pk=pk), 'Yearly Indicator Data')


@login_required
@permission_required('add_activityyeardata')
def activity_year_data_create(request):
	if not _require_icpd_admin(request):
		return redirect('icpd:dashboard')
	activity = get_object_or_404(Activity.objects.select_related('objective__commitment'), pk=request.GET.get('activity') or request.POST.get('activity'))
	if not _require_commitment_access(request, activity.objective.commitment):
		return redirect('icpd:dashboard')
	return _form_view(request, ActivityYearDataForm, 'Activity Expenditure', initial={'activity': activity.pk})


@login_required
@permission_required('change_activityyeardata')
def activity_year_data_update(request, pk):
	year_data = get_object_or_404(ActivityYearData, pk=pk)
	form_class = ActivityYearDataForm if _is_icpd_admin(request.user) else ActivityYearActualsForm
	return _form_view(request, form_class, 'Activity Expenditure', year_data)

# Create your views here.
