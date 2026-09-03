import json
from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth.models import Permission

from core.models import County, Quarter
from data_entry.models import DataEntry
from indicators.models import Indicator, ThematicArea
from reports.models import ReportAccessPolicy
from users.models import Role, User
from icpd.models import Activity, ActivityIndicator, Commitment, CommitmentNarrativeReport, IndicatorYearData, Objective


class ReportCatalogueTests(TestCase):
	def setUp(self):
		self.county = County.objects.create(
			name='Report County', code='041', headquarters='Report Town', region='central',
		)
		self.other_county = County.objects.create(
			name='Other County', code='042', headquarters='Other Town', region='central',
		)
		self.quarter = Quarter.objects.create(
			name='Q1 2026', fiscal_year='2025/2026', quarter_number=1,
			start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), submission_deadline=date(2026, 4, 30),
		)
		area = ThematicArea.objects.create(name='Report Area', code='REPORT')
		self.indicator = Indicator.objects.create(
			code='REPORT-001', name='Report indicator', thematic_area=area,
			data_type='count', unit='people', frequency='quarterly', target_value=10,
		)
		self.user = User.objects.create_superuser(
			username='report_admin', email='report@example.com', password='test-password',
		)
		self.user.counties.add(self.county)
		self.client.force_login(self.user)

	def test_preview_and_excel_export_render_for_a_report(self):
		DataEntry.objects.create(
			county=self.county, quarter=self.quarter, indicator=self.indicator,
			value='12', target_at_submission=10, status='approved',
		)

		preview = self.client.get('/report/data-entries/')
		export = self.client.get('/report/data-entries/export/excel/')

		self.assertContains(preview, 'Report indicator')
		self.assertEqual(export.status_code, 200)
		self.assertEqual(
			export['Content-Type'],
			'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
		)

	def test_reports_root_renders_the_user_scoped_dashboard(self):
		response = self.client.get('/dashboard/')

		self.assertContains(response, 'Dashboard')
		self.assertContains(response, 'Reports')
		self.assertContains(response, 'County Performance Map')
		self.assertContains(response, 'id="mapMetric"')
		self.assertContains(response, 'id="mapThematicArea"')
		self.assertContains(response, 'id="countyAnalysisModal"')
		self.assertContains(response, 'showCountyModal(feature.properties.COUNTY)')
		self.assertContains(response, 'pointer-events: auto !important')
		self.assertContains(response, 'const countyRenderer = L.canvas({ padding: 0.5 });')
		self.assertContains(response, 'bubblingMouseEvents: false')
		self.assertContains(response, 'mousemove: function(event)')
		self.assertContains(response, 'highlightCounty(event.target)')
		self.assertContains(response, "mapThematicArea.addEventListener('change', updateMapAnalysis)")
		self.assertContains(response, 'View Data Records')
		self.assertEqual(
			json.loads(response.context['county_map_data']),
			[{
				'id': self.county.id,
				'name': 'Report County',
				'approved': 0,
				'submitted': 0,
				'rejected': 0,
				'draft': 0,
				'indicators': 0,
				'thematic_areas': [],
				'total': 0,
				'met': 0,
				'percentage': 0,
			}],
		)
	def test_county_map_boundaries_are_available_to_dashboard_users(self):
		response = self.client.get('/dashboard/county-boundaries/')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.json()['features']), 47)

	def test_dashboard_total_entries_excludes_drafts(self):
		for status, code in (('approved', 'REPORT-101'), ('submitted', 'REPORT-102'), ('rejected', 'REPORT-103'), ('draft', 'REPORT-104')):
			indicator = Indicator.objects.create(
				code=code, name=f'{status.title()} indicator', thematic_area=self.indicator.thematic_area,
				data_type='count', unit='people', frequency='quarterly', target_value=10,
			)
			DataEntry.objects.create(
				county=self.county, quarter=self.quarter, indicator=indicator,
				value='12', target_at_submission=10, status=status,
			)

		response = self.client.get('/dashboard/')

		self.assertEqual(response.context['approved_entries'], 1)
		self.assertEqual(response.context['total_entries'], 3)
		self.assertEqual(
			json.loads(response.context['county_map_data']),
			[{
				'id': self.county.id,
				'name': 'Report County',
				'approved': 1,
				'submitted': 1,
				'rejected': 1,
				'draft': 1,
				'indicators': 4,
				'thematic_areas': ['Report Area'],
				'total': 1,
				'met': 1,
				'percentage': 100,
			}],
		)

	@patch('reports.views.timezone.localdate', return_value=date(2026, 2, 15))
	def test_dashboard_uses_the_quarter_containing_today(self, mocked_localdate):
		Quarter.objects.create(
			name='Q2 2026', fiscal_year='2025/2026', quarter_number=2,
			start_date=date(2026, 4, 1), end_date=date(2026, 6, 30), submission_deadline=date(2026, 7, 31),
		)

		response = self.client.get('/dashboard/')

		self.assertEqual(response.context['current_quarter'], self.quarter)
		self.assertEqual(response.context['current_quarter_label'], 'Q1 2026')
		self.assertContains(response, 'Q1 2026')
		mocked_localdate.assert_called_once()

	def test_catalogue_has_a_single_canonical_url(self):
		response = self.client.get('/report/')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.resolver_match.view_name, 'reports:report_list')

	def test_county_assignment_cannot_be_overridden_by_a_query_parameter(self):
		DataEntry.objects.create(
			county=self.county, quarter=self.quarter, indicator=self.indicator,
			value='12', target_at_submission=10, status='approved',
		)
		DataEntry.objects.create(
			county=self.other_county, quarter=self.quarter, indicator=self.indicator,
			value='20', target_at_submission=10, status='approved',
		)

		response = self.client.get(f'/report/data-entries/?county={self.other_county.pk}')

		self.assertContains(response, 'Report County')
		self.assertNotContains(response, 'Other County')

	def test_data_entry_report_supports_multiple_reporting_periods(self):
		second_quarter = Quarter.objects.create(
			name='Q2 2026', fiscal_year='2025/2026', quarter_number=2,
			start_date=date(2026, 4, 1), end_date=date(2026, 6, 30), submission_deadline=date(2026, 7, 31),
		)
		DataEntry.objects.create(
			county=self.county, quarter=self.quarter, indicator=self.indicator,
			value='12', target_at_submission=10, status='approved',
		)
		DataEntry.objects.create(
			county=self.county, quarter=second_quarter, indicator=self.indicator,
			value='15', target_at_submission=10, status='approved',
		)

		response = self.client.get('/report/data-entries/', {
			'quarter': [self.quarter.pk, second_quarter.pk],
		})

		self.assertContains(response, 'Q1 2026')
		self.assertContains(response, 'Q2 2026')

	def test_icpd_reports_use_the_current_icpd_indicator_hierarchy(self):
		commitment = Commitment.objects.create(title='ICPD Commitment')
		objective = Objective.objects.create(commitment=commitment, title='ICPD Objective')
		activity = Activity.objects.create(objective=objective, title='ICPD Activity')
		indicator = ActivityIndicator.objects.create(activity=activity, name='ICPD Indicator')
		IndicatorYearData.objects.create(
			activity_indicator=indicator, financial_year='2025/26', target_value=5,
		)

		performance = self.client.get('/report/icpd-performance/', {'financial_year': '2025/26'})
		comprehensive = self.client.get('/report/icpd-comprehensive/', {'commitment': commitment.pk})

		self.assertEqual(performance.status_code, 200)
		self.assertContains(performance, indicator.code)
		self.assertEqual(comprehensive.status_code, 200)
		self.assertContains(comprehensive, 'ICPD Commitment')

	def test_empty_icpd_report_uses_a_datatables_compatible_row(self):
		response = self.client.get('/report/icpd-plan/')

		self.assertContains(response, 'No records match these filters.')
		self.assertNotContains(response, 'colspan=')

	def test_icpd_performance_supports_multiple_objective_filters(self):
		commitment = Commitment.objects.create(title='ICPD Commitment')
		first_objective = Objective.objects.create(commitment=commitment, title='First Objective')
		second_objective = Objective.objects.create(commitment=commitment, title='Second Objective')
		for objective, indicator_name in ((first_objective, 'First Indicator'), (second_objective, 'Second Indicator')):
			activity = Activity.objects.create(objective=objective, title=f'{indicator_name} Activity')
			indicator = ActivityIndicator.objects.create(activity=activity, name=indicator_name)
			IndicatorYearData.objects.create(activity_indicator=indicator, financial_year='2025/26', target_value=5)

		response = self.client.get('/report/icpd-performance/', {
			'objective': [first_objective.pk, second_objective.pk],
		})

		self.assertContains(response, 'First Indicator')
		self.assertContains(response, 'Second Indicator')

	def test_restricted_report_is_visible_only_to_selected_users_or_roles(self):
		viewer_role = Role.objects.create(name='report_viewer', display_name='Report Viewer')
		viewer_role.permissions.add(Permission.objects.get(codename='view_reports'))
		viewer = User.objects.create_user(
			username='restricted_viewer', password='test-password', role=viewer_role,
			is_verified=True,
		)
		policy = ReportAccessPolicy.objects.create(report_key='data-entries', is_restricted=True)

		self.client.force_login(viewer)
		catalogue = self.client.get('/report/')
		preview = self.client.get('/report/data-entries/')

		self.assertNotContains(catalogue, 'M&E Data Entries')
		self.assertRedirects(preview, '/report/')

		policy.allowed_users.add(viewer)
		self.assertEqual(self.client.get('/report/data-entries/').status_code, 200)

		policy.allowed_users.clear()
		policy.allowed_roles.add(viewer_role)
		self.assertEqual(self.client.get('/report/data-entries/').status_code, 200)

	def test_icpd_narrative_report_expands_saved_submissions(self):
		commitment = Commitment.objects.create(title='Narrative Report Commitment')
		CommitmentNarrativeReport.objects.create(
			commitment=commitment,
			author=self.user,
			financial_year='2025/26',
			introduction='Narrative introduction.',
			executive_summary='Narrative summary.',
		)

		response = self.client.get('/report/icpd-narratives/', {'commitment': commitment.pk})

		self.assertContains(response, 'Narrative Report Commitment')
		self.assertContains(response, 'Narrative introduction.')
		self.assertContains(response, 'Export This Narrative to Word')
