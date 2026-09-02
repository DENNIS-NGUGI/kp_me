from django.test import TestCase
from django.utils import timezone
from datetime import date
from django.contrib.auth.models import Permission

from core.models import County, Quarter
from indicators.models import Indicator, ThematicArea
from users.models import Role, User

from .models import DataEntry


class DataEntryDetailTests(TestCase):
	def test_submitted_entry_detail_renders_for_an_approver(self):
		user = User.objects.create_superuser(
			username='data_approver',
			email='approver@example.com',
			password='test-password',
		)
		county = County.objects.create(
			name='Test County',
			code='001',
			headquarters='Test Town',
			region='central',
		)
		quarter = Quarter.objects.create(
			name='Q1 2026',
			fiscal_year='2026/2027',
			quarter_number=1,
			start_date=date(2026, 1, 1),
			end_date=date(2026, 3, 31),
			submission_deadline=date(2026, 4, 30),
		)
		area = ThematicArea.objects.create(name='Test Area', code='TEST')
		indicator = Indicator.objects.create(
			code='TEST-ENTRY-001',
			name='Test entry indicator',
			thematic_area=area,
			data_type='count',
			unit='people',
			frequency='quarterly',
		)
		entry = DataEntry.objects.create(
			county=county,
			quarter=quarter,
			indicator=indicator,
			value='10',
			status='submitted',
			submitted_by=user,
			submitted_at=timezone.now(),
		)
		self.client.force_login(user)

		response = self.client.get(f'/data-entry/{entry.pk}/')

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Entry Detail')


class DataEntryWorkflowTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_superuser(
			username='data_entry_admin',
			email='data-entry-admin@example.com',
			password='test-password',
		)
		self.county = County.objects.create(
			name='Workflow County',
			code='002',
			headquarters='Workflow Town',
			region='central',
		)
		self.quarter = Quarter.objects.create(
			name='Q2 2026',
			fiscal_year='2026/2027',
			quarter_number=2,
			start_date=date(2026, 4, 1),
			end_date=date(2026, 6, 30),
			submission_deadline=date(2026, 7, 31),
		)
		area = ThematicArea.objects.create(name='Workflow Area', code='WORKFLOW')
		self.indicator = Indicator.objects.create(
			code='WORKFLOW-001',
			name='Workflow indicator',
			thematic_area=area,
			data_type='count',
			unit='people',
			frequency='quarterly',
		)
		self.client.force_login(self.user)

	def test_selection_step_opens_the_entry_step(self):
		response = self.client.post('/data-entry/form/', {
			'county': self.county.pk,
			'quarter': self.quarter.pk,
			'selected_indicators': [self.indicator.pk],
			'action': 'continue',
		})

		self.assertRedirects(
			response,
			f'/data-entry/form/?step=enter&county={self.county.pk}&quarter={self.quarter.pk}&selected={self.indicator.pk}',
		)

	def test_draft_save_returns_to_the_filtered_entry_list(self):
		response = self.client.post('/data-entry/form/', {
			'county': self.county.pk,
			'quarter': self.quarter.pk,
			'selected_indicators': [self.indicator.pk],
			f'indicator_{self.indicator.pk}': '25',
			f'notes_{self.indicator.pk}': 'Saved for review',
			'action': 'draft',
		})

		self.assertRedirects(response, f'/data-entry/?county={self.county.pk}&quarter={self.quarter.pk}')
		entry = DataEntry.objects.get(county=self.county, quarter=self.quarter, indicator=self.indicator)
		self.assertEqual(entry.status, 'draft')
		self.assertEqual(entry.notes, 'Saved for review')


class CountyDataScopeTests(TestCase):
	def test_unfiltered_form_does_not_show_empty_entry_rows(self):
		user = User.objects.create_superuser(
			username='unfiltered_admin',
			email='unfiltered-admin@example.com',
			password='test-password',
		)
		area = ThematicArea.objects.create(name='Unfiltered Area', code='UNFILTERED')
		Indicator.objects.create(
			code='UNFILTERED-001', name='Unfiltered indicator', thematic_area=area,
			data_type='count', unit='people', frequency='quarterly',
		)
		self.client.force_login(user)

		response = self.client.get('/data-entry/form/')

		self.assertContains(response, 'Choose a county and quarter')
		self.assertNotContains(response, 'No entry')

	def test_county_assigned_user_sees_existing_county_entries(self):
		county = County.objects.create(
			name='County Scope', code='003', headquarters='Scope Town', region='central'
		)
		quarter = Quarter.objects.create(
			name='Q3 2026', fiscal_year='2026/2027', quarter_number=3,
			start_date=date(2026, 7, 1), end_date=date(2026, 9, 30),
			submission_deadline=date(2026, 10, 31),
		)
		area = ThematicArea.objects.create(name='Scope Area', code='SCOPE')
		indicator = Indicator.objects.create(
			code='SCOPE-001', name='Scope indicator', thematic_area=area,
			data_type='count', unit='people', frequency='quarterly',
		)
		role = Role.objects.create(name='county_reporter', display_name='County Reporter')
		role.permissions.add(
			Permission.objects.get(codename='view_dataentry'),
			Permission.objects.get(codename='add_dataentry'),
		)
		user = User.objects.create_user(
			username='county_reporter', password='test-password', role=role, county=county
		)
		DataEntry.objects.create(
			county=county, quarter=quarter, indicator=indicator, value='30', status='submitted'
		)
		self.client.force_login(user)

		list_response = self.client.get('/data-entry/')
		form_response = self.client.get(
			f'/data-entry/form/?step=select&county={county.pk}&quarter={quarter.pk}'
		)

		self.assertContains(list_response, 'SCOPE-001')
		self.assertContains(form_response, 'Submitted')
		self.assertNotContains(form_response, 'No entry')
