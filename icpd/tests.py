import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from django.db import IntegrityError
from django.contrib.auth.models import Permission
from django.urls import reverse

from users.models import Role, User

from .models import Activity, ActivityIndicator, ActivityYearData, Commitment, CommitmentNarrativeReport, IndicatorYearData, Objective
from .models import CommitmentAccessPolicy
from .forms import IndicatorYearActualsForm, IndicatorYearDataForm


class IcpdPlanningModelTests(TestCase):
	def setUp(self):
		commitment = Commitment.objects.create(title='Improve adolescent health')
		objective = Objective.objects.create(
			commitment=commitment,
			title='Expand access to youth services',
		)
		self.activity = Activity.objects.create(
			objective=objective,
			title='Establish constituency innovation hubs',
			budget_amount=4000000000,
			responsibility='MoH',
		)
		self.activity_indicator = ActivityIndicator.objects.create(
			activity=self.activity,
			name='Innovation hubs established',
			baseline_value=0,
			baseline_year='2020/21',
		)

	def test_activity_has_one_budget_and_multiple_indicators(self):
		second_indicator = ActivityIndicator.objects.create(
			activity=self.activity,
			name='Young people reached',
		)

		self.assertEqual(self.activity.budget_amount, 4000000000)
		self.assertEqual(self.activity.activity_indicators.count(), 2)
		self.assertEqual(self.activity_indicator.code, f'ICPD-{self.activity_indicator.pk:04d}')
		self.assertEqual(second_indicator.code, f'ICPD-{second_indicator.pk:04d}')

	def test_only_one_yearly_record_per_indicator_and_financial_year(self):
		IndicatorYearData.objects.create(
			activity_indicator=self.activity_indicator,
			financial_year='2021/22',
			target_value=12,
			achievement_value=4,
			status='on_track',
		)

		with self.assertRaises(IntegrityError):
			IndicatorYearData.objects.create(
				activity_indicator=self.activity_indicator,
				financial_year='2021/22',
			)

	def test_cumulative_values_and_annual_activity_expenditure_are_tracked(self):
		IndicatorYearData.objects.create(
			activity_indicator=self.activity_indicator,
			financial_year='2021/22',
			target_value=12,
			achievement_value=4,
		)
		IndicatorYearData.objects.create(
			activity_indicator=self.activity_indicator,
			financial_year='2022/23',
			target_value=8,
			achievement_value=7,
		)
		ActivityYearData.objects.create(
			activity=self.activity,
			financial_year='2021/22',
			expenditure_amount=25,
		)

		self.assertEqual(self.activity_indicator.cumulative_target_value, 20)
		self.assertEqual(self.activity_indicator.cumulative_achievement_value, 11)

		with self.assertRaises(IntegrityError):
			ActivityYearData.objects.create(
				activity=self.activity,
				financial_year='2021/22',
			)

	def test_contributor_form_exposes_only_annual_actuals_and_status(self):
		self.assertEqual(
			list(IndicatorYearActualsForm().fields),
			['achievement_value', 'status', 'remarks'],
		)

	def test_administrator_annual_target_form_excludes_actual_fields(self):
		self.assertEqual(
			list(IndicatorYearDataForm().fields),
			['activity_indicator', 'financial_year', 'target_value'],
		)

	def test_json_import_converts_direct_kes_budget_to_millions(self):
		payload = {
			'commitments': [{
				'title': 'Imported Commitment',
				'objectives': [{
					'title': 'Imported Objective',
					'activities': [{
						'title': 'Imported Activity',
						'budget_amount': 4000000000,
						'indicators': [{'name': 'Imported Indicator', 'annual_targets': []}],
					}],
				}],
			}],
		}
		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as json_file:
			json.dump(payload, json_file)
			json_path = Path(json_file.name)
		try:
			call_command('import_icpd_plan', str(json_path))
		finally:
			json_path.unlink()

		activity = Activity.objects.get(title='Imported Activity')
		self.assertEqual(activity.budget_amount, 4000)
		self.assertEqual(activity.activity_indicators.get().code, 'ICPD-0002')

	def test_json_import_skips_existing_commitment(self):
		payload = {'commitments': [{'title': 'Existing Commitment'}]}
		Commitment.objects.create(title='Existing Commitment')
		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as json_file:
			json.dump(payload, json_file)
			json_path = Path(json_file.name)
		try:
			call_command('import_icpd_plan', str(json_path))
		finally:
			json_path.unlink()

		self.assertEqual(Commitment.objects.filter(title='Existing Commitment').count(), 1)


class IcpdPermissionTests(TestCase):
	def test_activity_indicator_create_url_resolves_for_an_icpd_administrator(self):
		user = User.objects.create_superuser(
			username='activity_indicator_admin',
			email='activity-indicator-admin@example.com',
			password='test-password',
		)
		commitment = Commitment.objects.create(title='Test Commitment')
		objective = Objective.objects.create(commitment=commitment, title='Test Objective')
		activity = Activity.objects.create(objective=objective, title='Test Activity')
		self.client.force_login(user)

		response = self.client.get('/icpd/activity-indicators/add/', {'activity': activity.pk})

		self.assertEqual(response.status_code, 200)

	def test_dashboard_requires_view_commitment_permission(self):
		role = Role.objects.create(name='icpd_planner', display_name='ICPD Planner')
		user = User.objects.create_user(username='planner', password='test-password', role=role)

		self.client.force_login(user)
		denied_response = self.client.get('/icpd/')
		self.assertEqual(denied_response.status_code, 302)

		role.permissions.add(Permission.objects.get(codename='view_commitment'))
		allowed_response = self.client.get('/icpd/')
		self.assertEqual(allowed_response.status_code, 200)

	def test_objective_create_and_update_redirect_to_parent_commitment(self):
		user = User.objects.create_superuser(
			username='icpd_admin',
			email='icpd-admin@example.com',
			password='test-password',
		)
		commitment = Commitment.objects.create(title='Test Commitment')
		self.client.force_login(user)

		create_response = self.client.post(
			reverse('icpd:objective_create'),
			{'commitment': commitment.pk, 'title': 'Test Objective', 'sort_order': 1},
		)
		objective = Objective.objects.get(title='Test Objective')
		detail_url = reverse('icpd:commitment_detail', args=[commitment.pk])
		self.assertRedirects(create_response, detail_url)

		update_response = self.client.post(
			reverse('icpd:objective_update', args=[objective.pk]),
			{'commitment': commitment.pk, 'title': 'Updated Objective', 'sort_order': 1},
		)
		self.assertRedirects(update_response, detail_url)
		objective.refresh_from_db()
		self.assertEqual(objective.title, 'Updated Objective')

	def test_restricted_commitment_requires_an_assigned_user_or_role(self):
		commitment = Commitment.objects.create(title='Restricted Commitment')
		role = Role.objects.create(name='assigned_icpd_user')
		role.permissions.add(Permission.objects.get(codename='view_commitment'))
		user = User.objects.create_user(username='unassigned_icpd', password='test-password', role=role)
		policy = CommitmentAccessPolicy.objects.create(commitment=commitment, is_restricted=True)
		self.client.force_login(user)

		self.assertNotContains(self.client.get(reverse('icpd:dashboard')), 'Restricted Commitment')
		self.assertRedirects(self.client.get(reverse('icpd:commitment_detail', args=[commitment.pk])), reverse('icpd:dashboard'))

		policy.allowed_roles.add(role)
		self.assertContains(self.client.get(reverse('icpd:dashboard')), 'Restricted Commitment')
		self.assertEqual(self.client.get(reverse('icpd:commitment_detail', args=[commitment.pk])).status_code, 200)


class IcpdReportingFlowTests(TestCase):
	def test_assigned_user_can_save_a_commitment_narrative(self):
		commitment = Commitment.objects.create(title='Narrative Commitment')
		role = Role.objects.create(name='narrative_contributor')
		role.permissions.add(Permission.objects.get(codename='view_commitment'))
		user = User.objects.create_user(username='narrative_author', password='test-password', role=role)
		policy = CommitmentAccessPolicy.objects.create(commitment=commitment, is_restricted=True)
		policy.allowed_users.add(user)
		self.client.force_login(user)

		response = self.client.post(reverse('icpd:report_entry'), {
			'tab': 'narrative',
			'commitment': commitment.pk,
			'introduction': 'The commitment is on track.',
			'abbreviations': 'ICPD: International Conference on Population and Development.',
			'executive_summary': 'Implementation remains on track.',
			'other_actor_contributions': 'County partners supported delivery.',
			'facilitating_factors': 'Clear coordination enabled progress.',
			'challenges': 'Limited resources slowed progress.',
			'opportunities': 'New partnerships can enhance implementation.',
			'conclusion_and_recommendations': 'Continue county coordination.',
			'references': 'NCPD quarterly monitoring data, 2026.',
		})

		self.assertRedirects(response, f'{reverse("icpd:report_entry")}?tab=narrative&commitment={commitment.pk}&financial_year=2025/26')
		report = CommitmentNarrativeReport.objects.get(commitment=commitment, author=user)
		self.assertEqual(report.introduction, 'The commitment is on track.')

	def test_narrative_export_is_hidden_until_a_narrative_is_saved(self):
		user = User.objects.create_superuser(username='empty_narrative_author', email='empty@example.com', password='test-password')
		commitment = Commitment.objects.create(title='Empty Narrative Commitment')
		self.client.force_login(user)

		response = self.client.get(reverse('icpd:report_entry'), {
			'tab': 'narrative',
			'commitment': commitment.pk,
			'financial_year': '2025/26',
		})

		self.assertContains(response, 'Save Narrative')
		self.assertNotContains(response, 'Export Word')
		self.assertFalse(CommitmentNarrativeReport.objects.exists())

	def test_narrative_word_export_uses_the_selected_reporting_year(self):
		user = User.objects.create_superuser(username='narrative_exporter', email='export@example.com', password='test-password')
		commitment = Commitment.objects.create(title='Export Commitment')
		narrative = CommitmentNarrativeReport.objects.create(
			commitment=commitment,
			author=user,
			financial_year='2025/26',
			introduction='On track.',
			executive_summary='Strong progress.',
		)
		self.client.force_login(user)

		response = self.client.get(reverse('icpd:narrative_report_export'), {
			'commitment': commitment.pk,
			'financial_year': '2025/26',
			'narrative': narrative.pk,
		})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			response['Content-Type'],
			'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
		)
	def test_report_entry_only_offers_the_selected_activity_indicator_years(self):
		user = User.objects.create_superuser(
			username='icpd_reporter', email='reporter@example.com', password='test-password',
		)
		commitment = Commitment.objects.create(title='Configured Commitment')
		objective = Objective.objects.create(commitment=commitment, title='Configured Objective')
		activity = Activity.objects.create(objective=objective, title='Configured Activity')
		indicator = ActivityIndicator.objects.create(
			activity=activity, code='ICPD-CFG-01', name='Configured Activity Indicator',
		)
		IndicatorYearData.objects.create(
			activity_indicator=indicator, financial_year='2025/26', target_value=10,
		)
		self.client.force_login(user)

		response = self.client.get(reverse('icpd:report_entry'), {
			'commitment': commitment.pk,
			'objective': objective.pk,
			'activity': activity.pk,
			'activity_indicator': indicator.pk,
		})

		self.assertContains(response, 'Configured Activity Indicator')
		self.assertContains(response, '2025/26')
		self.assertNotContains(response, '2029/30')

	def test_report_entry_loads_actuals_form_for_selected_financial_year(self):
		user = User.objects.create_superuser(
			username='year_selector', email='year-selector@example.com', password='test-password',
		)
		commitment = Commitment.objects.create(title='Configured Commitment')
		objective = Objective.objects.create(commitment=commitment, title='Configured Objective')
		activity = Activity.objects.create(objective=objective, title='Configured Activity')
		indicator = ActivityIndicator.objects.create(
			activity=activity, code='ICPD-CFG-SELECT', name='Configured Activity Indicator',
		)
		IndicatorYearData.objects.create(
			activity_indicator=indicator, financial_year='2025/26', target_value=10,
		)
		self.client.force_login(user)

		response = self.client.get(reverse('icpd:report_entry'), {
			'commitment': commitment.pk,
			'objective': objective.pk,
			'activity': activity.pk,
			'activity_indicator': indicator.pk,
			'financial_year': '2025/26',
		})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Achievement Value')

	def test_reporter_creates_expenditure_when_submitting_actuals(self):
		user = User.objects.create_superuser(
			username='actuals_reporter', email='actuals@example.com', password='test-password',
		)
		commitment = Commitment.objects.create(title='Configured Commitment')
		objective = Objective.objects.create(commitment=commitment, title='Configured Objective')
		activity = Activity.objects.create(objective=objective, title='Configured Activity')
		indicator = ActivityIndicator.objects.create(
			activity=activity, code='ICPD-CFG-02', name='Configured Activity Indicator',
		)
		year_data = IndicatorYearData.objects.create(
			activity_indicator=indicator, financial_year='2025/26', target_value=10,
		)
		self.client.force_login(user)

		response = self.client.post(reverse('icpd:report_entry'), {
			'commitment': commitment.pk,
			'objective': objective.pk,
			'activity': activity.pk,
			'activity_indicator': indicator.pk,
			'financial_year': '2025/26',
			'achievement_value': '7',
			'status': 'on_track',
			'expenditure-expenditure_amount': '25',
			'expenditure-remarks': 'Funds released.',
		})

		self.assertEqual(response.status_code, 302)
		year_data.refresh_from_db()
		self.assertEqual(year_data.achievement_value, 7)
		self.assertEqual(ActivityYearData.objects.get(activity=activity, financial_year='2025/26').expenditure_amount, 25)
