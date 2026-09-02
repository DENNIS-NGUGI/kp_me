from django.test import TestCase

from partners.models import Partner

from .forms import CollaboratingPartnerForm


class CollaboratingPartnerFormTests(TestCase):
	def setUp(self):
		self.partner = Partner.objects.create(
			name='Registered Partner',
			code='PARTNER-001',
			contact_person='Jane Doe',
			contact_email='jane@example.com',
			contact_phone='+254700000000',
		)

	def test_registered_partner_sets_canonical_partner_name(self):
		form = CollaboratingPartnerForm(data={'partner': self.partner.pk, 'partner_name': ''})

		self.assertTrue(form.is_valid())
		self.assertEqual(form.cleaned_data['partner_name'], self.partner.name)

	def test_unlisted_partner_name_is_allowed(self):
		form = CollaboratingPartnerForm(data={'partner': '', 'partner_name': 'New Organization'})

		self.assertTrue(form.is_valid())
