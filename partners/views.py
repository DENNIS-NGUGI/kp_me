from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.utils import timezone
from .models import Partner, Project, ProjectMilestone, ProjectReport
from indicators.models import Indicator
from core.models import County
from users.models import Role

from django.contrib.auth import get_user_model
User = get_user_model()

# ===== PERMISSION HELPER FUNCTIONS =====
def is_admin_or_superuser(user):
    """Check if user is admin or superuser"""
    return user.is_superuser or (user.role and user.role.name == 'admin')

def is_ncpd_or_admin(user):
    """Check if user is NCPD, admin, or superuser"""
    return user.is_superuser or (user.role and user.role.name in ['admin', 'ncpd_me'])

def is_partner_user(user):
    """Check if user is a partner"""
    return user.role and user.role.name == 'partner'


# ===== PARTNER VIEWS =====

@login_required
def partner_list(request):
    """List all partners"""
    user = request.user
    
    # RBAC: Partner users only see their partner
    if is_partner_user(user):
        partners = user.partners.all()
    else:
        partners = Partner.objects.all()
    
    # Filters
    partner_type = request.GET.get('type')
    status = request.GET.get('status')
    
    if partner_type:
        partners = partners.filter(partner_type=partner_type)
    if status:
        partners = partners.filter(status=status)
    
    context = {
        'partners': partners,
        'partner_types': Partner.PARTNER_TYPES,
        'status_choices': Partner.STATUS_CHOICES,
        'selected_type': partner_type,
        'selected_status': status,
    }
    return render(request, 'partners/list.html', context)


@login_required
def partner_detail(request, pk):
    """Partner detail page"""
    partner = get_object_or_404(Partner, pk=pk)
    user = request.user
    
    # RBAC: Partner users only see their partner
    if is_partner_user(user) and partner not in user.partners.all():
        messages.error(request, 'You do not have permission to view this partner.')
        return redirect('partners:list')
    
    projects = partner.projects.filter(is_active=True)
    active_projects = projects.filter(status='active')
    completed_projects = projects.filter(status='completed')
    
    # Project statistics
    total_budget = projects.aggregate(total=Sum('budget'))['total'] or 0
    total_expenditure = projects.aggregate(total=Sum('expenditure'))['total'] or 0
    
    context = {
        'partner': partner,
        'projects': projects,
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'total_budget': total_budget,
        'total_expenditure': total_expenditure,
        'budget_utilization': round((total_expenditure / total_budget * 100) if total_budget > 0 else 0),
        'project_count': projects.count(),
        'active_count': active_projects.count(),
    }
    return render(request, 'partners/detail.html', context)


@login_required
@user_passes_test(is_ncpd_or_admin)
def partner_add(request):
    """Add a new partner"""
    if request.method == 'POST':
        try:
            partner = Partner(
                code=request.POST.get('code'),
                name=request.POST.get('name'),
                partner_type=request.POST.get('partner_type'),
                description=request.POST.get('description'),
                contact_person=request.POST.get('contact_person'),
                contact_email=request.POST.get('contact_email'),
                contact_phone=request.POST.get('contact_phone'),
                address=request.POST.get('address'),
                website=request.POST.get('website'),
                status=request.POST.get('status'),
                created_by=request.user,
            )
            partner.save()
            
            # Add counties
            county_ids = request.POST.getlist('counties')
            if county_ids:
                partner.counties.set(county_ids)
            
            # Add users - filter by partner role using new Role system
            user_ids = request.POST.getlist('users')
            if user_ids:
                partner_users = User.objects.filter(id__in=user_ids, role__name='partner')
                partner.users.set(partner_users)
            
            messages.success(request, f'Partner {partner.name} added successfully!')
            return redirect('partners:detail', pk=partner.pk)
        except Exception as e:
            messages.error(request, f'Error adding partner: {str(e)}')
    
    counties = County.objects.filter(is_active=True)
    partner_role = Role.objects.filter(name='partner').first()
    users = User.objects.filter(role=partner_role) if partner_role else User.objects.none()
    
    context = {
        'counties': counties,
        'users': users,
        'partner_types': Partner.PARTNER_TYPES,
        'status_choices': Partner.STATUS_CHOICES,
    }
    return render(request, 'partners/form.html', context)


@login_required
@user_passes_test(is_ncpd_or_admin)
def partner_edit(request, pk):
    """Edit partner"""
    partner = get_object_or_404(Partner, pk=pk)
    
    if request.method == 'POST':
        try:
            partner.code = request.POST.get('code')
            partner.name = request.POST.get('name')
            partner.partner_type = request.POST.get('partner_type')
            partner.description = request.POST.get('description')
            partner.contact_person = request.POST.get('contact_person')
            partner.contact_email = request.POST.get('contact_email')
            partner.contact_phone = request.POST.get('contact_phone')
            partner.address = request.POST.get('address')
            partner.website = request.POST.get('website')
            partner.status = request.POST.get('status')
            partner.save()
            
            county_ids = request.POST.getlist('counties')
            partner.counties.set(county_ids)
            
            user_ids = request.POST.getlist('users')
            if user_ids:
                partner_users = User.objects.filter(id__in=user_ids, role__name='partner')
                partner.users.set(partner_users)
            else:
                partner.users.clear()
            
            messages.success(request, f'Partner {partner.name} updated successfully!')
            return redirect('partners:detail', pk=partner.pk)
        except Exception as e:
            messages.error(request, f'Error updating partner: {str(e)}')
    
    counties = County.objects.filter(is_active=True)
    partner_role = Role.objects.filter(name='partner').first()
    users = User.objects.filter(role=partner_role) if partner_role else User.objects.none()
    
    context = {
        'partner': partner,
        'counties': counties,
        'users': users,
        'partner_types': Partner.PARTNER_TYPES,
        'status_choices': Partner.STATUS_CHOICES,
    }
    return render(request, 'partners/form.html', context)


# ===== PROJECT VIEWS =====

@login_required
def project_list(request):
    """List all projects"""
    user = request.user
    
    # RBAC
    if is_partner_user(user):
        partner_ids = user.partners.values_list('id', flat=True)
        projects = Project.objects.filter(partner__in=partner_ids)
    else:
        projects = Project.objects.all()
    
    # Filters
    status = request.GET.get('status')
    partner_id = request.GET.get('partner')
    
    if status:
        projects = projects.filter(status=status)
    if partner_id:
        projects = projects.filter(partner_id=partner_id)
    
    context = {
        'projects': projects,
        'status_choices': Project.STATUS_CHOICES,
        'partners': Partner.objects.filter(status='active'),
    }
    return render(request, 'partners/project_list.html', context)


@login_required
def project_detail(request, pk):
    """Project detail page"""
    project = get_object_or_404(Project, pk=pk)
    user = request.user
    
    # RBAC
    if is_partner_user(user) and project.partner not in user.partners.all():
        messages.error(request, 'You do not have permission to view this project.')
        return redirect('partners:project_list')
    
    milestones = project.milestones.all()
    completed_milestones = milestones.filter(is_completed=True)
    
    # Get linked indicators with data
    indicators = project.indicators.all()
    
    context = {
        'project': project,
        'milestones': milestones,
        'completed_milestones': completed_milestones,
        'progress': project.get_progress(),
        'days_remaining': project.get_days_remaining(),
        'budget_utilization': project.get_budget_utilization(),
        'indicators': indicators,
    }
    return render(request, 'partners/project_detail.html', context)


@login_required
@user_passes_test(is_ncpd_or_admin)
def project_add(request):
    """Add a new project"""
    if request.method == 'POST':
        try:
            project = Project(
                code=request.POST.get('code'),
                name=request.POST.get('name'),
                partner_id=request.POST.get('partner'),
                description=request.POST.get('description'),
                start_date=request.POST.get('start_date'),
                end_date=request.POST.get('end_date'),
                budget=request.POST.get('budget') or 0,
                status=request.POST.get('status'),
                project_lead=request.POST.get('project_lead'),
                project_email=request.POST.get('project_email'),
                project_phone=request.POST.get('project_phone'),
                created_by=request.user,
            )
            project.save()
            
            # Add indicators
            indicator_ids = request.POST.getlist('indicators')
            if indicator_ids:
                project.indicators.set(indicator_ids)
            
            # Add counties
            county_ids = request.POST.getlist('counties')
            if county_ids:
                project.counties.set(county_ids)
            
            messages.success(request, f'Project {project.name} added successfully!')
            return redirect('partners:project_detail', pk=project.pk)
        except Exception as e:
            messages.error(request, f'Error adding project: {str(e)}')
    
    partners = Partner.objects.filter(status='active')
    indicators = Indicator.objects.filter(is_active=True)
    counties = County.objects.filter(is_active=True)
    
    context = {
        'partners': partners,
        'indicators': indicators,
        'counties': counties,
        'status_choices': Project.STATUS_CHOICES,
    }
    return render(request, 'partners/project_form.html', context)


@login_required
@user_passes_test(is_ncpd_or_admin)
def project_edit(request, pk):
    """Edit project"""
    project = get_object_or_404(Project, pk=pk)
    
    if request.method == 'POST':
        try:
            project.code = request.POST.get('code')
            project.name = request.POST.get('name')
            project.partner_id = request.POST.get('partner')
            project.description = request.POST.get('description')
            project.start_date = request.POST.get('start_date')
            project.end_date = request.POST.get('end_date')
            project.budget = request.POST.get('budget') or 0
            project.expenditure = request.POST.get('expenditure') or 0
            project.status = request.POST.get('status')
            project.is_active = request.POST.get('is_active') == 'on'
            project.project_lead = request.POST.get('project_lead')
            project.project_email = request.POST.get('project_email')
            project.project_phone = request.POST.get('project_phone')
            project.save()
            
            indicator_ids = request.POST.getlist('indicators')
            project.indicators.set(indicator_ids)
            
            county_ids = request.POST.getlist('counties')
            project.counties.set(county_ids)
            
            messages.success(request, f'Project {project.name} updated successfully!')
            return redirect('partners:project_detail', pk=project.pk)
        except Exception as e:
            messages.error(request, f'Error updating project: {str(e)}')
    
    partners = Partner.objects.filter(status='active')
    indicators = Indicator.objects.filter(is_active=True)
    counties = County.objects.filter(is_active=True)
    
    context = {
        'project': project,
        'partners': partners,
        'indicators': indicators,
        'counties': counties,
        'status_choices': Project.STATUS_CHOICES,
    }
    return render(request, 'partners/project_form.html', context)


@login_required
def project_milestone_add(request, project_pk):
    """Add a milestone to a project"""
    project = get_object_or_404(Project, pk=project_pk)
    user = request.user
    
    # Check permission
    if is_partner_user(user) and project.partner not in user.partners.all():
        messages.error(request, 'You do not have permission to modify this project.')
        return redirect('partners:project_detail', pk=project_pk)
    
    if request.method == 'POST':
        try:
            ProjectMilestone.objects.create(
                project=project,
                name=request.POST.get('name'),
                description=request.POST.get('description'),
                due_date=request.POST.get('due_date'),
                order=request.POST.get('order', 0),
            )
            messages.success(request, 'Milestone added successfully!')
        except Exception as e:
            messages.error(request, f'Error adding milestone: {str(e)}')
        
        return redirect('partners:project_detail', pk=project_pk)
    
    return render(request, 'partners/milestone_form.html', {'project': project})


@login_required
def project_milestone_complete(request, pk):
    """Mark milestone as complete"""
    milestone = get_object_or_404(ProjectMilestone, pk=pk)
    user = request.user
    
    # Check permission
    project = milestone.project
    if is_partner_user(user) and project.partner not in user.partners.all():
        messages.error(request, 'You do not have permission to modify this milestone.')
        return redirect('partners:project_detail', pk=project.pk)
    
    milestone.is_completed = True
    milestone.completed_date = timezone.now().date()
    milestone.save()
    
    messages.success(request, f'Milestone "{milestone.name}" completed!')
    return redirect('partners:project_detail', pk=milestone.project.pk)


@login_required
def project_dashboard(request):
    """Partner/Project Dashboard"""
    user = request.user
    
    # RBAC
    if is_partner_user(user):
        partner_ids = user.partners.values_list('id', flat=True)
        projects = Project.objects.filter(partner__in=partner_ids)
        partners = Partner.objects.filter(id__in=partner_ids)
    else:
        projects = Project.objects.all()
        partners = Partner.objects.filter(status='active')
    
    # Statistics
    total_projects = projects.count()
    active_projects = projects.filter(status='active').count()
    completed_projects = projects.filter(status='completed').count()
    
    # Recent projects
    recent_projects = projects.order_by('-created_at')[:5]
    
    context = {
        'total_projects': total_projects,
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'recent_projects': recent_projects,
        'partners': partners,
        'user_role': user.role.name if user.role else 'None',
    }
    return render(request, 'partners/dashboard.html', context)