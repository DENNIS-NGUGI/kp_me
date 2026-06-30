from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.utils import timezone
from .models import Partner, Project, ProjectMilestone, ProjectReport
from indicators.models import Indicator
from core.models import County
from users.models import Role
from users.permissions import get_partner_queryset_filter, get_project_queryset_filter

from django.contrib.auth import get_user_model
User = get_user_model()


# ===== PARTNER VIEWS =====

@login_required
def partner_list(request):
    """List all partners - Uses centralized permissions"""
    user = request.user
    
    # Use centralized filter
    partners = Partner.objects.filter(get_partner_queryset_filter(user))
    
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
        'can_manage': user.can_manage_partners(),
        'can_view': user.can_view_partners(),
    }
    return render(request, 'partners/list.html', context)


@login_required
def partner_detail(request, pk):
    """Partner detail page"""
    partner = get_object_or_404(Partner, pk=pk)
    user = request.user
    
    # Check if user can view this partner
    if not user.can_view_partners():
        messages.error(request, 'You do not have permission to view partners.')
        return redirect('partners:list')
    
    # Partner users can only see their partner
    if user.is_partner_user and partner not in user.partners.all():
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
        'can_manage': user.can_manage_partners(),
    }
    return render(request, 'partners/detail.html', context)


@login_required
def partner_add(request):
    """Add a new partner - Uses centralized permissions"""
    user = request.user
    
    if not user.can_manage_partners():
        messages.error(request, 'You do not have permission to add partners.')
        return redirect('partners:list')
    
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
            
            # Add users
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
def partner_edit(request, pk):
    """Edit partner - Uses centralized permissions"""
    user = request.user
    
    if not user.can_manage_partners():
        messages.error(request, 'You do not have permission to edit partners.')
        return redirect('partners:list')
    
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


@login_required
def partner_delete(request, pk):
    """Delete partner - Uses centralized permissions"""
    user = request.user
    
    if not user.can_manage_partners():
        messages.error(request, 'You do not have permission to delete partners.')
        return redirect('partners:list')
    
    partner = get_object_or_404(Partner, pk=pk)
    
    # Check if partner has projects
    if partner.projects.exists():
        messages.error(request, f'Cannot delete "{partner.name}" - it has associated projects.')
        return redirect('partners:detail', pk=partner.pk)
    
    if request.method == 'POST':
        partner_name = partner.name
        partner.delete()
        messages.success(request, f'Partner "{partner_name}" deleted successfully!')
        return redirect('partners:list')
    
    context = {'partner': partner}
    return render(request, 'partners/delete.html', context)


# ===== PROJECT VIEWS =====

@login_required
def project_list(request):
    """List all projects - Uses centralized permissions"""
    user = request.user
    
    # Use centralized filter
    projects = Project.objects.filter(get_project_queryset_filter(user))
    
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
        'can_manage': user.can_manage_projects(),
    }
    return render(request, 'partners/project_list.html', context)


@login_required
def project_detail(request, pk):
    """Project detail page"""
    project = get_object_or_404(Project, pk=pk)
    user = request.user
    
    # Check if user can view this project
    if not user.can_view_projects():
        messages.error(request, 'You do not have permission to view projects.')
        return redirect('partners:project_list')
    
    # Partner users can only see their partner's projects
    if user.is_partner_user and project.partner not in user.partners.all():
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
        'can_manage': user.can_manage_projects(),
    }
    return render(request, 'partners/project_detail.html', context)


@login_required
def project_add(request):
    """Add a new project - Uses centralized permissions"""
    user = request.user
    
    if not user.can_manage_projects():
        messages.error(request, 'You do not have permission to add projects.')
        return redirect('partners:project_list')
    
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
def project_edit(request, pk):
    """Edit project - Uses centralized permissions"""
    user = request.user
    
    if not user.can_manage_projects():
        messages.error(request, 'You do not have permission to edit projects.')
        return redirect('partners:project_list')
    
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
def project_delete(request, pk):
    """Delete project - Uses centralized permissions"""
    user = request.user
    
    if not user.can_manage_projects():
        messages.error(request, 'You do not have permission to delete projects.')
        return redirect('partners:project_list')
    
    project = get_object_or_404(Project, pk=pk)
    
    # Check if project has reports or milestones
    if project.reports.exists():
        messages.error(request, f'Cannot delete "{project.name}" - it has associated reports.')
        return redirect('partners:project_detail', pk=project.pk)
    
    if request.method == 'POST':
        project_name = project.name
        project.delete()
        messages.success(request, f'Project "{project_name}" deleted successfully!')
        return redirect('partners:project_list')
    
    context = {'project': project}
    return render(request, 'partners/project_delete.html', context)


@login_required
def project_milestone_add(request, project_pk):
    """Add a milestone to a project - Uses centralized permissions"""
    project = get_object_or_404(Project, pk=project_pk)
    user = request.user
    
    if not user.can_manage_projects():
        messages.error(request, 'You do not have permission to add milestones.')
        return redirect('partners:project_detail', pk=project_pk)
    
    # Partner users can only add milestones to their partner's projects
    if user.is_partner_user and project.partner not in user.partners.all():
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
    """Mark milestone as complete - Uses centralized permissions"""
    milestone = get_object_or_404(ProjectMilestone, pk=pk)
    user = request.user
    project = milestone.project
    
    if not user.can_manage_projects():
        messages.error(request, 'You do not have permission to complete milestones.')
        return redirect('partners:project_detail', pk=project.pk)
    
    # Partner users can only complete milestones for their partner's projects
    if user.is_partner_user and project.partner not in user.partners.all():
        messages.error(request, 'You do not have permission to modify this milestone.')
        return redirect('partners:project_detail', pk=project.pk)
    
    milestone.is_completed = True
    milestone.completed_date = timezone.now().date()
    milestone.save()
    
    messages.success(request, f'Milestone "{milestone.name}" completed!')
    return redirect('partners:project_detail', pk=milestone.project.pk)


@login_required
def project_dashboard(request):
    """Partner/Project Dashboard - Uses centralized permissions"""
    user = request.user
    
    # Use centralized filters
    partners = Partner.objects.filter(get_partner_queryset_filter(user))
    projects = Project.objects.filter(get_project_queryset_filter(user))
    
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
        'can_manage_partners': user.can_manage_partners(),
        'can_manage_projects': user.can_manage_projects(),
    }
    return render(request, 'partners/dashboard.html', context)