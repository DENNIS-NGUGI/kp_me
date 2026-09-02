from django.test import TestCase
from unittest.mock import patch
from datetime import date

from django.contrib.auth.models import Permission

from core.models import County, Quarter
from data_entry.models import DataEntry
from indicators.models import Indicator, ThematicArea
from users.models import Role, User

from .utils import notify_submissions


class SubmissionNotificationTests(TestCase):
	@patch('notifications.utils.create_notification')
	def test_batch_submission_notifies_each_recipient_once(self, create_notification):
		county = County.objects.create(
			name='Notification County', code='004', headquarters='Notify Town', region='central'
		)
		quarter = Quarter.objects.create(
			name='Q4 2026', fiscal_year='2026/2027', quarter_number=4,
			start_date=date(2026, 10, 1), end_date=date(2026, 12, 31),
			submission_deadline=date(2027, 1, 31),
		)
		area = ThematicArea.objects.create(name='Notify Area', code='NOTIFY')
		indicator = Indicator.objects.create(
			code='NOTIFY-001', name='Notify indicator', thematic_area=area,
			data_type='count', unit='people', frequency='quarterly',
		)
		second_indicator = Indicator.objects.create(
			code='NOTIFY-002', name='Second notify indicator', thematic_area=area,
			data_type='count', unit='people', frequency='quarterly',
		)
		submitter = User.objects.create_user(username='submitter', password='test-password')
		approver_role = Role.objects.create(name='notification_approver')
		approver_role.permissions.add(Permission.objects.get(codename='can_approve_data'))
		User.objects.create_user(username='approver', password='test-password', role=approver_role)
		entries = [
			DataEntry.objects.create(county=county, quarter=quarter, indicator=indicator, value='10'),
			DataEntry.objects.create(county=county, quarter=quarter, indicator=second_indicator, value='20'),
		]

		notify_submissions(entries, submitter)

		self.assertEqual(create_notification.call_count, 2)
