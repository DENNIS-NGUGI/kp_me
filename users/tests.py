from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import User


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PasswordResetTests(TestCase):
	def test_password_reset_sends_a_reset_link_for_an_active_user(self):
		User.objects.create_user(
			username='reset_user',
			email='reset@example.com',
			password='initial-password',
		)

		response = self.client.post(reverse('users:password_reset'), {'email': 'reset@example.com'})

		self.assertRedirects(response, reverse('users:password_reset_done'))
		self.assertEqual(len(mail.outbox), 1)
		self.assertIn('/users/password-reset/', mail.outbox[0].body)
