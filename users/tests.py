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


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AdminUserRegistrationTests(TestCase):
	def setUp(self):
		self.admin = User.objects.create_superuser(
			username='administrator',
			email='admin@example.com',
			password='AdminPassword123!',
		)
		self.client.force_login(self.admin)

	def test_admin_can_create_user_and_send_temporary_password(self):
		response = self.client.post(reverse('users:user_add'), {
			'username': 'new_user',
			'email': 'new.user@example.com',
			'first_name': 'New',
			'last_name': 'User',
		})

		self.assertRedirects(response, reverse('users:user_management'))
		user = User.objects.get(username='new_user')
		self.assertTrue(user.is_verified)
		self.assertTrue(user.is_email_verified)
		self.assertTrue(user.force_password_change)
		self.assertEqual(len(mail.outbox), 1)
		self.assertIn('Username: new_user', mail.outbox[0].body)

	def test_temporary_password_user_is_restricted_to_password_change(self):
		user = User.objects.create_user(
			username='temporary_user',
			email='temporary@example.com',
			password='TemporaryPassword123!',
			force_password_change=True,
		)
		self.client.force_login(user)

		response = self.client.get(reverse('users:profile'))

		self.assertRedirects(response, reverse('users:change_password'))

	def test_temporary_password_user_can_change_password_and_continue(self):
		user = User.objects.create_user(
			username='changing_user',
			email='changing@example.com',
			password='TemporaryPassword123!',
			force_password_change=True,
		)
		self.client.force_login(user)

		response = self.client.post(reverse('users:change_password'), {
			'current_password': 'TemporaryPassword123!',
			'new_password1': 'UpdatedPassword123!',
			'new_password2': 'UpdatedPassword123!',
		})

		self.assertRedirects(response, reverse('reports:dashboard'))
		user.refresh_from_db()
		self.assertFalse(user.force_password_change)
		self.assertTrue(user.check_password('UpdatedPassword123!'))
