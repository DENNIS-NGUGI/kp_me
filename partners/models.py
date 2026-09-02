from django.db import models
from django.contrib.auth import get_user_model
from core.models import County
from indicators.models import Indicator

User = get_user_model()


class Partner(models.Model):
    """Implementing Partner Organization"""
    
    PARTNER_TYPES = (
        ('ngo', 'NGO'),
        ('cbo', 'CBO'),
        ('fbo', 'FBO'),
        ('government', 'Government'),
        ('private', 'Private Sector'),
        ('academic', 'Academic/Research'),
        ('development', 'Development Partner'),
        ('other', 'Other'),
    )
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending Approval'),
        ('suspended', 'Suspended'),
    )
    
    # Basic Info
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, unique=True, help_text="Partner code e.g., P-001")
    partner_type = models.CharField(max_length=20, choices=PARTNER_TYPES, default='ngo')
    description = models.TextField(blank=True)
    
    # Contact Info
    contact_person = models.CharField(max_length=100)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    
    # Location
    counties = models.ManyToManyField(County, blank=True, related_name='partners')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    registration_date = models.DateField(auto_now_add=True)
    
    # Users associated with this partner
    users = models.ManyToManyField(User, blank=True, related_name='partners')
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_partners')
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_project_count(self):
        return self.projects.filter(is_active=True).count()
    
    def get_total_budget(self):
        return self.projects.filter(is_active=True).aggregate(
            total=models.Sum('budget')
        )['total'] or 0


class Project(models.Model):
    """Projects implemented by partners"""
    
    STATUS_CHOICES = (
        ('planning', 'Planning'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('suspended', 'Suspended'),
        ('cancelled', 'Cancelled'),
    )
    
    # Basic Info
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True, help_text="Project code e.g., PRJ-001")
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='projects')
    description = models.TextField(blank=True)
    
    # Timeline
    start_date = models.DateField()
    end_date = models.DateField()
    actual_end_date = models.DateField(null=True, blank=True)
    
    # Budget
    budget = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    expenditure = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning')
    is_active = models.BooleanField(default=True)
    
    # Links
    indicators = models.ManyToManyField(Indicator, blank=True, related_name='projects')
    counties = models.ManyToManyField(County, blank=True, related_name='projects')
    
    # Contact
    project_lead = models.CharField(max_length=100, blank=True)
    project_email = models.EmailField(blank=True)
    project_phone = models.CharField(max_length=20, blank=True)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_projects')
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def get_progress(self):
        """Calculate project progress based on milestones"""
        milestones = self.milestones.filter(is_completed=True)
        total = self.milestones.count()
        if total == 0:
            return 0
        return round((milestones.count() / total) * 100)
    
    def get_days_remaining(self):
        from django.utils import timezone
        today = timezone.now().date()
        if self.status == 'completed':
            return 0
        delta = self.end_date - today
        return delta.days if delta.days > 0 else 0
    
    def get_budget_utilization(self):
        if self.budget == 0:
            return 0
        return round((self.expenditure / self.budget) * 100)


class ProjectMilestone(models.Model):
    """Project milestones for tracking progress"""
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milestones')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    
    # Ordering
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order', 'due_date']
    
    def __str__(self):
        return f"{self.project.code} - {self.name}"
    
    def is_overdue(self):
        from django.utils import timezone
        if self.is_completed:
            return False
        return timezone.now().date() > self.due_date


class ProjectReport(models.Model):
    """Project progress reports"""
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='reports')
    title = models.CharField(max_length=200)
    report_date = models.DateField(auto_now_add=True)
    report_period_start = models.DateField()
    report_period_end = models.DateField()
    achievements = models.TextField()
    challenges = models.TextField(blank=True)
    next_actions = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    
    # Links to data entries
    data_entries = models.ManyToManyField('data_entry.DataEntry', blank=True, related_name='project_reports')
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-report_date']
    
    def __str__(self):
        return f"{self.project.code} - {self.title}"
