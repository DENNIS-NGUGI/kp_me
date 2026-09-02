from django.db import models
from django.conf import settings


class ReportAccessPolicy(models.Model):
	"""Controls which users and roles may open a catalogue report."""

	report_key = models.CharField(max_length=100, unique=True)
	is_restricted = models.BooleanField(default=False)
	allowed_roles = models.ManyToManyField(
		'users.Role',
		blank=True,
		related_name='report_access_policies',
	)
	allowed_users = models.ManyToManyField(
		settings.AUTH_USER_MODEL,
		blank=True,
		related_name='report_access_policies',
	)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['report_key']
		verbose_name = 'Report access policy'
		verbose_name_plural = 'Report access policies'

	def __str__(self):
		return self.report_key

# Create your models here.
