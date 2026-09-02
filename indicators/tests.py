from django.test import TestCase
from django.urls import reverse

from users.models import User

from .models import Indicator, SustainableDevelopmentGoal, ThematicArea


class IndicatorSdgTests(TestCase):
	def test_indicator_can_link_to_multiple_sdgs(self):
		area = ThematicArea.objects.create(code='TEST', name='Test Area')
		indicator = Indicator.objects.create(
			code='TEST-001',
			name='Test indicator',
			thematic_area=area,
			data_type='count',
			unit='people',
			frequency='annual',
		)
		sdg_three = SustainableDevelopmentGoal.objects.create(number=3, title='Good Health')
		sdg_five = SustainableDevelopmentGoal.objects.create(number=5, title='Gender Equality')

		indicator.sdgs.add(sdg_three, sdg_five)

		self.assertEqual(list(indicator.sdgs.values_list('number', flat=True)), [3, 5])

	def test_sdg_list_route_is_not_captured_as_an_indicator_code(self):
		user = User.objects.create_superuser(
			username='sdg_admin',
			email='sdg-admin@example.com',
			password='test-password',
		)
		self.client.force_login(user)

		response = self.client.get(reverse('indicators:sdg_list'))

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'indicators/sdg_list.html')
