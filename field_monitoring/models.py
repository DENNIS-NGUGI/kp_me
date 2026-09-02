"""
Field Monitoring Visit Report Models
Captures NCPD field visit monitoring data including:
- Visit details and organizing entity
- Visiting team members
- People met during visit
- Services provided
- Findings and recommendations
- Challenges and best practices
- Collaborating partners
"""

from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from core.models import County
from django.contrib.auth import get_user_model
from indicators.models import Indicator

User = get_user_model()


class FieldVisitReport(models.Model):
    """
    Main field monitoring visit report capturing all visit information
    """
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('reviewed', 'Reviewed'),
        ('approved', 'Approved'),
        ('archived', 'Archived'),
    )
    
    # Report metadata
    report_code = models.CharField(
        max_length=50,
        unique=True,
        help_text=_("Auto-generated report code (e.g., FMR-2025-001)")
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        help_text=_("Report approval status")
    )
    
    # Visit organization details
    organization_name = models.CharField(
        max_length=255,
        help_text=_("Name of the organization/CBO being monitored")
    )
    county = models.ForeignKey(
        County,
        on_delete=models.PROTECT,
        related_name='field_visits',
        help_text=_("County where visit took place")
    )
    location_details = models.TextField(
        help_text=_("Specific location/facility details")
    )
    
    # Visit timing
    visit_date = models.DateField(
        help_text=_("Date of the field visit")
    )
    last_visit_date = models.DateField(
        null=True,
        blank=True,
        help_text=_("Date of the previous visit")
    )
    report_date = models.DateField(
        help_text=_("Date report was compiled")
    )
    
    # Report compiler
    report_compiled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='compiled_reports',
        help_text=_("Person who compiled the report")
    )
    report_submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_reports',
        help_text=_("Person who submitted the report")
    )
    
    # Data collection methods
    data_collection_methods = models.TextField(
        blank=True,
        help_text=_("Methods used to collect data (e.g., interviews, observations)")
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_visits',
        help_text=_("Person who approved the report")
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When report was approved")
    )
    
    class Meta:
        ordering = ['-visit_date']
        indexes = [
            models.Index(fields=['county', '-visit_date']),
            models.Index(fields=['status']),
            models.Index(fields=['organization_name']),
        ]
        verbose_name = _('Field Visit Report')
        verbose_name_plural = _('Field Visit Reports')
        permissions = [
            ('can_approve_field_visit', _('Can approve field visits')),
            ('can_export_field_visit', _('Can export field visit reports')),
        ]
    
    def __str__(self):
        return f"{self.report_code} - {self.organization_name} ({self.visit_date})"
    
    def clean(self):
        """Validate report data"""
        if self.report_date and self.visit_date:
            if self.report_date < self.visit_date:
                raise ValidationError(
                    _('Report date cannot be before visit date')
                )
        
        if self.last_visit_date and self.visit_date:
            if self.last_visit_date > self.visit_date:
                raise ValidationError(
                    _('Last visit date cannot be after current visit date')
                )
    
    def save(self, *args, **kwargs):
        """Auto-generate report code if not provided"""
        if not self.report_code:
            # Generate report code: FMR-YYYY-XXX
            year = self.visit_date.year
            count = FieldVisitReport.objects.filter(
                visit_date__year=year
            ).count() + 1
            self.report_code = f"FMR-{year}-{count:03d}"
        
        self.full_clean()
        super().save(*args, **kwargs)


class VisitingTeamMember(models.Model):
    """
    Members of the visiting/monitoring team
    """
    visit = models.ForeignKey(
        FieldVisitReport,
        on_delete=models.CASCADE,
        related_name='visiting_team_members',
        help_text=_("Associated field visit report")
    )
    name = models.CharField(
        max_length=255,
        help_text=_("Full name of team member")
    )
    title_organization = models.CharField(
        max_length=255,
        help_text=_("Title/Position and Organization")
    )
    telephone = models.CharField(
        max_length=20,
        blank=True,
        help_text=_("Contact telephone number")
    )
    email = models.EmailField(
        blank=True,
        help_text=_("Email address")
    )
    
    class Meta:
        ordering = ['name']
        verbose_name = _('Visiting Team Member')
        verbose_name_plural = _('Visiting Team Members')
    
    def __str__(self):
        return f"{self.name} - {self.title_organization}"


class PersonMet(models.Model):
    """
    Key persons/stakeholders met during the visit
    """
    visit = models.ForeignKey(
        FieldVisitReport,
        on_delete=models.CASCADE,
        related_name='persons_met',
        help_text=_("Associated field visit report")
    )
    name = models.CharField(
        max_length=255,
        help_text=_("Full name of person met")
    )
    title = models.CharField(
        max_length=255,
        help_text=_("Title/Position in organization")
    )
    
    class Meta:
        ordering = ['name']
        verbose_name = _('Person Met')
        verbose_name_plural = _('Persons Met')
    
    def __str__(self):
        return f"{self.name} ({self.title})"


class ServiceProvided(models.Model):
    """
    Services/Activities provided by the Programme/CBO with findings
    """
    visit = models.ForeignKey(
        FieldVisitReport,
        on_delete=models.CASCADE,
        related_name='services_provided',
        help_text=_("Associated field visit report")
    )
    service_name = models.CharField(
        max_length=255,
        help_text=_("Name of service/activity")
    )
    indicator = models.ForeignKey(
        Indicator,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='field_visit_services',
        help_text=_("Associated indicator (if applicable)")
    )
    findings = models.TextField(
        help_text=_("Findings observed during visit")
    )
    recommended_action = models.TextField(
        help_text=_("Recommended actions based on findings")
    )
    
    class Meta:
        ordering = ['service_name']
        verbose_name = _('Service Provided')
        verbose_name_plural = _('Services Provided')
    
    def __str__(self):
        return f"{self.service_name} - {self.visit.organization_name}"


class Challenge(models.Model):
    """
    Challenges and issues identified during the visit with recommendations
    """
    visit = models.ForeignKey(
        FieldVisitReport,
        on_delete=models.CASCADE,
        related_name='challenges',
        help_text=_("Associated field visit report")
    )
    challenge_description = models.TextField(
        help_text=_("Description of challenge/issue identified")
    )
    recommendation = models.TextField(
        help_text=_("Recommended solution or action to address challenge")
    )
    priority = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        default='medium',
        help_text=_("Priority level for addressing challenge")
    )
    
    class Meta:
        ordering = ['-priority', 'challenge_description']
        verbose_name = _('Challenge')
        verbose_name_plural = _('Challenges')
    
    def __str__(self):
        return f"{self.challenge_description[:50]}... ({self.priority})"


class BestPractice(models.Model):
    """
    Best practices and success stories identified during the visit
    """
    visit = models.ForeignKey(
        FieldVisitReport,
        on_delete=models.CASCADE,
        related_name='best_practices',
        help_text=_("Associated field visit report")
    )
    practice_description = models.TextField(
        help_text=_("Description of best practice/success story")
    )
    lessons_learned = models.TextField(
        blank=True,
        help_text=_("Key lessons from this practice")
    )
    replicable = models.BooleanField(
        default=True,
        help_text=_("Can this practice be replicated in other areas?")
    )
    
    class Meta:
        ordering = ['practice_description']
        verbose_name = _('Best Practice')
        verbose_name_plural = _('Best Practices')
    
    def __str__(self):
        return f"{self.practice_description[:50]}..."


class CollaboratingPartner(models.Model):
    """
    Partners and stakeholders collaborating with the organization
    """
    visit = models.ForeignKey(
        FieldVisitReport,
        on_delete=models.CASCADE,
        related_name='collaborating_partners',
        help_text=_("Associated field visit report")
    )
    partner = models.ForeignKey(
        'partners.Partner',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='field_visit_collaborations',
        help_text=_('Select a registered partner when available'),
    )
    partner_name = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Name of collaborating organization/partner")
    )
    partnership_nature = models.TextField(
        blank=True,
        help_text=_("Nature of partnership/collaboration")
    )
    contact_person = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Primary contact person")
    )
    contact_details = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Phone/email for contact")
    )
    
    class Meta:
        ordering = ['partner_name']
        verbose_name = _('Collaborating Partner')
        verbose_name_plural = _('Collaborating Partners')
    
    def __str__(self):
        return self.partner.name if self.partner else self.partner_name


class FieldVisitAttachment(models.Model):
    """
    Supporting documents, photos, or evidence from field visit
    """
    visit = models.ForeignKey(
        FieldVisitReport,
        on_delete=models.CASCADE,
        related_name='attachments',
        help_text=_("Associated field visit report")
    )
    DOCUMENT_TYPES = [
        ('photo', 'Photograph/Evidence'),
        ('document', 'Document/Report'),
        ('video', 'Video Recording'),
        ('data', 'Data/Spreadsheet'),
    ]
    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPES,
        help_text=_("Type of attachment")
    )
    file = models.FileField(
        upload_to='field_visits/%Y/%m/',
        help_text=_("Attached file")
    )
    description = models.TextField(
        help_text=_("Description of attachment")
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = _('Field Visit Attachment')
        verbose_name_plural = _('Field Visit Attachments')
    
    def __str__(self):
        return f"{self.document_type} - {self.description[:50]}"
