"""
Field Monitoring Views - CRUD Operations for Field Visit Reports
Phase 2: Front-end Views, Templates, and Export functionality
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Count
from django.utils import timezone
from django.conf import settings
from django.core.paginator import Paginator
from datetime import timedelta

from .models import (
    FieldVisitReport,
    VisitingTeamMember,
    PersonMet,
    ServiceProvided,
    Challenge,
    BestPractice,
    CollaboratingPartner,
    FieldVisitAttachment,
)
from .forms import (
    FieldVisitReportForm,
    VisitingTeamMemberFormSet,
    PersonMetFormSet,
    ServiceProvidedFormSet,
    ChallengeFormSet,
    BestPracticeFormSet,
    CollaboratingPartnerFormSet,
    FieldVisitAttachmentFormSet,
)
from users.decorators import permission_required
from core.models import County

# ============================================
# MULTI-STEP WIZARD CONFIGURATION
# ============================================

# Each step after 'info' maps to one inline formset; 'review' has no form of its own.
FORM_STEPS = [
    {'key': 'info', 'label': 'Visit Info', 'icon': 'bi-info-circle'},
    {'key': 'team', 'label': 'Visiting Team', 'icon': 'bi-people'},
    {'key': 'persons', 'label': 'Persons Met', 'icon': 'bi-person-badge'},
    {'key': 'services', 'label': 'Services Provided', 'icon': 'bi-clipboard-check'},
    {'key': 'challenges', 'label': 'Challenges', 'icon': 'bi-exclamation-triangle'},
    {'key': 'practices', 'label': 'Best Practices', 'icon': 'bi-star'},
    {'key': 'partners', 'label': 'Partners', 'icon': 'bi-handshake'},
    {'key': 'attachments', 'label': 'Attachments', 'icon': 'bi-paperclip'},
    {'key': 'review', 'label': 'Review & Submit', 'icon': 'bi-check2-circle'},
]
STEP_KEYS = [s['key'] for s in FORM_STEPS]

FORMSET_CLASSES = {
    'team': VisitingTeamMemberFormSet,
    'persons': PersonMetFormSet,
    'services': ServiceProvidedFormSet,
    'challenges': ChallengeFormSet,
    'practices': BestPracticeFormSet,
    'partners': CollaboratingPartnerFormSet,
    'attachments': FieldVisitAttachmentFormSet,
}


def _build_steps_nav(current_step, has_report=True):
    """Return the stepper list, previous/next step keys, and completion percentage"""
    idx = STEP_KEYS.index(current_step)
    steps = [
        {
            **s,
            'number': i + 1,
            'is_current': s['key'] == current_step,
            'is_done': i < idx,
            'is_clickable': has_report and (i < idx or s['key'] == current_step),
        }
        for i, s in enumerate(FORM_STEPS)
    ]
    prev_step = STEP_KEYS[idx - 1] if idx > 0 else None
    next_step = STEP_KEYS[idx + 1] if idx < len(STEP_KEYS) - 1 else None
    progress_percent = round(idx / (len(STEP_KEYS) - 1) * 100)
    return steps, prev_step, next_step, progress_percent


def _redirect_to_step(pk, step):
    url = reverse('field_monitoring:field_visit_update', args=[pk])
    return redirect(f'{url}?step={step}' if step else url)


# ============================================
# VISIBILITY SCOPING
# ============================================

def _can_view_all_reports(user):
    """Admins and approvers can see every report regardless of owner/status"""
    return user.is_superuser or user.has_any_permission(
        'can_approve_field_visit',
        'can_manage_county_data',
    )


def _get_visible_reports(user):
    """
    Scope reports to what the user is allowed to see:
    - Admins/approvers: everything
    - Everyone else: their own reports (any status) plus finalized
      (reviewed/approved/archived) reports from their county.
      Draft and submitted reports of other users stay private.
    """
    base = FieldVisitReport.objects.select_related('county', 'report_compiled_by')

    if _can_view_all_reports(user):
        return base

    own_reports = Q(report_compiled_by=user)

    finalized = Q(status__in=['reviewed', 'approved', 'archived'])
    if getattr(user, 'county', None):
        finalized &= Q(county=user.county)
    else:
        finalized &= Q(pk__in=[])

    return base.filter(own_reports | finalized).distinct()


# ============================================
# LIST VIEW - All Field Visit Reports
# ============================================

@login_required
def field_visit_list(request):
    """List all field visit reports with filtering and search"""
    user = request.user
    
    # Base queryset scoped to what this user is allowed to see
    reports = _get_visible_reports(user).prefetch_related(
        'visiting_team_members',
        'services_provided',
        'challenges',
        'best_practices'
    ).order_by('-visit_date')
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        reports = reports.filter(
            Q(report_code__icontains=search_query) |
            Q(organization_name__icontains=search_query) |
            Q(location_details__icontains=search_query)
        )
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        reports = reports.filter(status=status_filter)
    
    # Filter by county
    county_filter = request.GET.get('county', '')
    if county_filter:
        reports = reports.filter(county_id=county_filter)
    
    # Filter by date range
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        reports = reports.filter(visit_date__gte=date_from)
    if date_to:
        reports = reports.filter(visit_date__lte=date_to)
    
    # Get filter options
    counties = County.objects.filter(is_active=True)
    status_choices = FieldVisitReport.STATUS_CHOICES
    
    # Pagination
    paginator = Paginator(reports, 25)  # 25 reports per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'reports': page_obj.object_list,
        'counties': counties,
        'status_choices': status_choices,
        'search_query': search_query,
        'status_filter': status_filter,
        'county_filter': county_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'field_monitoring/list.html', context)


# ============================================
# CREATE VIEW - New Field Visit Report
# ============================================

@login_required
@permission_required('add_fieldvisitreport')
def field_visit_create(request):
    """Step 1 of the wizard: capture basic visit info, then create the draft"""
    
    if request.method == 'POST':
        form = FieldVisitReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.report_compiled_by = request.user
            report.save()
            messages.success(request, f'Draft {report.report_code} created. Continue filling in the details.')
            return _redirect_to_step(report.id, 'team')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = FieldVisitReportForm()
    
    steps, prev_step, next_step, progress_percent = _build_steps_nav('info', has_report=False)
    context = {
        'form': form,
        'report': None,
        'steps': steps,
        'current_step': 'info',
        'prev_step': prev_step,
        'next_step': next_step,
        'progress_percent': progress_percent,
        'title': 'Field Visit Report',
        'action': 'Create',
    }
    
    return render(request, 'field_monitoring/form_step.html', context)


# ============================================
# DETAIL VIEW - View Field Visit Report
# ============================================

@login_required
def field_visit_detail(request, pk):
    """View detailed field visit report"""
    report = get_object_or_404(FieldVisitReport, pk=pk)
    
    # RBAC: Only owner, approvers/admins, or (once finalized) same-county users can view
    if not _get_visible_reports(request.user).filter(pk=report.pk).exists():
        messages.error(request, 'You do not have permission to view this report.')
        return redirect('field_monitoring:field_visit_list')
    
    # Get related data
    team_members = report.visiting_team_members.all()
    persons_met = report.persons_met.all()
    services = report.services_provided.all()
    challenges = report.challenges.all().order_by('-priority')
    practices = report.best_practices.all()
    partners = report.collaborating_partners.all()
    attachments = report.attachments.all()
    
    # Statistics
    total_challenges = challenges.count()
    critical_challenges = challenges.filter(priority='critical').count()
    high_priority_challenges = challenges.filter(priority='high').count()
    replicable_practices = practices.filter(replicable=True).count()
    
    is_owner = report.report_compiled_by_id == request.user.id
    can_approve = request.user.has_permission('can_approve_field_visit')
    
    context = {
        'report': report,
        'team_members': team_members,
        'persons_met': persons_met,
        'services': services,
        'challenges': challenges,
        'practices': practices,
        'partners': partners,
        'attachments': attachments,
        'is_owner': is_owner,
        'can_approve': can_approve,
        'stats': {
            'total_team_members': team_members.count(),
            'total_persons_met': persons_met.count(),
            'total_services': services.count(),
            'total_challenges': total_challenges,
            'critical_challenges': critical_challenges,
            'high_priority_challenges': high_priority_challenges,
            'total_practices': practices.count(),
            'replicable_practices': replicable_practices,
            'total_partners': partners.count(),
            'total_attachments': attachments.count(),
        }
    }
    
    return render(request, 'field_monitoring/detail.html', context)


# ============================================
# UPDATE VIEW - Edit Field Visit Report
# ============================================

@login_required
@permission_required('change_fieldvisitreport')
def field_visit_update(request, pk):
    """
    Step-by-step wizard for editing a field visit report.
    Each step saves immediately (the report stays in 'draft'/'submitted' status),
    so progress is never lost even if the user leaves mid-way.
    """
    report = get_object_or_404(FieldVisitReport, pk=pk)
    
    # RBAC: Only the owner or an admin/approver can edit
    if report.report_compiled_by_id != request.user.id and not _can_view_all_reports(request.user):
        messages.error(request, 'You do not have permission to edit this report.')
        return redirect('field_monitoring:field_visit_list')
    
    # Only allow editing if draft or submitted
    if report.status not in ['draft', 'submitted']:
        messages.error(request, 'Can only edit draft or submitted reports.')
        return redirect('field_monitoring:field_visit_detail', pk=report.id)
    
    step = request.GET.get('step') or request.POST.get('step') or 'info'
    if step not in STEP_KEYS:
        step = 'info'
    
    steps, prev_step, next_step, progress_percent = _build_steps_nav(step)
    form = None
    formset = None
    review_stats = None
    
    if step == 'info':
        if request.method == 'POST':
            form = FieldVisitReportForm(request.POST, instance=report)
            if form.is_valid():
                form.save()
                if request.POST.get('save_exit'):
                    messages.success(request, 'Progress saved.')
                    return redirect('field_monitoring:field_visit_detail', pk=report.id)
                return _redirect_to_step(report.id, next_step)
            messages.error(request, 'Please correct the errors below.')
        else:
            form = FieldVisitReportForm(instance=report)
    
    elif step == 'review':
        review_stats = {
            'team_members': report.visiting_team_members.count(),
            'persons_met': report.persons_met.count(),
            'services': report.services_provided.count(),
            'challenges': report.challenges.count(),
            'practices': report.best_practices.count(),
            'partners': report.collaborating_partners.count(),
            'attachments': report.attachments.count(),
        }
    
    else:
        FormSetClass = FORMSET_CLASSES[step]
        if request.method == 'POST':
            formset = FormSetClass(request.POST, request.FILES, instance=report)
            if formset.is_valid():
                formset.save()
                if request.POST.get('save_exit'):
                    messages.success(request, 'Progress saved.')
                    return redirect('field_monitoring:field_visit_detail', pk=report.id)
                return _redirect_to_step(report.id, next_step)
            messages.error(request, 'Please correct the errors below.')
        else:
            formset = FormSetClass(instance=report)
    
    context = {
        'report': report,
        'form': form,
        'formset': formset,
        'review_stats': review_stats,
        'is_owner': report.report_compiled_by_id == request.user.id,
        'steps': steps,
        'current_step': step,
        'prev_step': prev_step,
        'next_step': next_step,
        'progress_percent': progress_percent,
        'title': report.report_code,
        'action': 'Update',
    }
    
    return render(request, 'field_monitoring/form_step.html', context)



# ============================================
# DELETE VIEW - Delete Field Visit Report
# ============================================

@login_required
@permission_required('delete_fieldvisitreport')
def field_visit_delete(request, pk):
    """Delete a field visit report"""
    report = get_object_or_404(FieldVisitReport, pk=pk)
    
    # RBAC: Only the owner or an admin/approver can delete
    if report.report_compiled_by_id != request.user.id and not _can_view_all_reports(request.user):
        messages.error(request, 'You do not have permission to delete this report.')
        return redirect('field_monitoring:field_visit_list')
    
    # Only allow deleting if draft
    if report.status != 'draft':
        messages.error(request, 'Can only delete draft reports.')
        return redirect('field_monitoring:field_visit_detail', pk=report.id)
    
    if request.method == 'POST':
        report_code = report.report_code
        report.delete()
        messages.success(request, f'Field visit report {report_code} deleted successfully!')
        return redirect('field_monitoring:field_visit_list')
    
    context = {'report': report}
    return render(request, 'field_monitoring/confirm_delete.html', context)


# ============================================
# STATUS UPDATE ACTIONS
# ============================================

@login_required
@permission_required('change_fieldvisitreport')
def field_visit_submit(request, pk):
    """Submit a field visit report for review"""
    report = get_object_or_404(FieldVisitReport, pk=pk)
    
    # Only the owner can submit their own draft
    if report.report_compiled_by_id != request.user.id and not _can_view_all_reports(request.user):
        messages.error(request, 'You do not have permission to submit this report.')
        return redirect('field_monitoring:field_visit_detail', pk=report.id)
    
    if report.status != 'draft':
        messages.error(request, 'Only draft reports can be submitted.')
        return redirect('field_monitoring:field_visit_detail', pk=report.id)
    
    report.status = 'submitted'
    report.report_submitted_by = request.user
    report.save()
    
    messages.success(request, f'Report {report.report_code} submitted for review!')
    return redirect('field_monitoring:field_visit_detail', pk=report.id)


@login_required
@permission_required('can_approve_field_visit')
def field_visit_approve(request, pk):
    """Approve a field visit report"""
    report = get_object_or_404(FieldVisitReport, pk=pk)
    
    # 'reviewed' is an optional intermediate step; approvers can act straight from 'submitted'
    if report.status not in ['submitted', 'reviewed']:
        messages.error(request, 'Only submitted or reviewed reports can be approved.')
        return redirect('field_monitoring:field_visit_detail', pk=report.id)
    
    report.status = 'approved'
    report.approved_by = request.user
    report.approved_at = timezone.now()
    report.save()
    
    messages.success(request, f'Report {report.report_code} approved!')
    return redirect('field_monitoring:field_visit_detail', pk=report.id)


@login_required
@permission_required('can_approve_field_visit')
def field_visit_reject(request, pk):
    """Reject a field visit report (send back for revision)"""
    report = get_object_or_404(FieldVisitReport, pk=pk)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        if not reason:
            messages.error(request, 'Please provide a reason for rejection.')
            return redirect('field_monitoring:field_visit_detail', pk=report.id)
        
        report.status = 'draft'
        report.save()
        
        messages.success(request, f'Report {report.report_code} returned for revision. Reason: {reason}')
        return redirect('field_monitoring:field_visit_detail', pk=report.id)
    
    context = {'report': report}
    return render(request, 'field_monitoring/reject.html', context)


# ============================================
# EXPORT FUNCTIONALITY
# ============================================

@login_required
def field_visit_export_word(request, pk):
    """Export field visit report to Word (.docx)"""
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
    
    report = get_object_or_404(FieldVisitReport, pk=pk)
    
    # RBAC check: same visibility rules as detail view
    if not _get_visible_reports(request.user).filter(pk=report.pk).exists():
        messages.error(request, 'You do not have permission to export this report.')
        return redirect('field_monitoring:field_visit_list')
    
    try:
        # Create Document
        doc = Document()

        logo_path = settings.BASE_DIR / 'static' / 'images' / 'logo.png'
        if logo_path.exists():
            logo = doc.add_picture(str(logo_path), width=Inches(2.0))
            logo.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        
        # Header
        title = doc.add_heading('FIELD MONITORING VISIT REPORT', 0)
        title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        
        # Report metadata
        doc.add_heading('Report Information', level=1)
        table = doc.add_table(rows=8, cols=2)
        table.style = 'Light Grid Accent 1'
        
        cells = table.rows[0].cells
        cells[0].text = 'Report Code'
        cells[1].text = report.report_code
        
        cells = table.rows[1].cells
        cells[0].text = 'Status'
        cells[1].text = report.get_status_display()
        
        cells = table.rows[2].cells
        cells[0].text = 'Organization Name'
        cells[1].text = report.organization_name
        
        cells = table.rows[3].cells
        cells[0].text = 'County'
        cells[1].text = report.county.name
        
        cells = table.rows[4].cells
        cells[0].text = 'Location'
        cells[1].text = report.location_details or 'N/A'
        
        cells = table.rows[5].cells
        cells[0].text = 'Visit Date'
        cells[1].text = report.visit_date.strftime('%Y-%m-%d')
        
        cells = table.rows[6].cells
        cells[0].text = 'Report Date'
        cells[1].text = report.report_date.strftime('%Y-%m-%d')
        
        cells = table.rows[7].cells
        cells[0].text = 'Compiled By'
        cells[1].text = report.report_compiled_by.get_full_name() if report.report_compiled_by else 'N/A'
        
        # Visiting Team
        doc.add_heading('Visiting Team Members', level=1)
        if report.visiting_team_members.exists():
            table = doc.add_table(rows=1, cols=4)
            table.style = 'Light Grid Accent 1'
            header_cells = table.rows[0].cells
            header_cells[0].text = 'Name'
            header_cells[1].text = 'Title/Organization'
            header_cells[2].text = 'Telephone'
            header_cells[3].text = 'Email'
            
            for member in report.visiting_team_members.all():
                row_cells = table.add_row().cells
                row_cells[0].text = member.name or ''
                row_cells[1].text = member.title_organization or ''
                row_cells[2].text = member.telephone or ''
                row_cells[3].text = member.email or ''
        else:
            doc.add_paragraph('No team members recorded.')

        # Persons Met
        doc.add_heading('Persons Met', level=1)
        if report.persons_met.exists():
            table = doc.add_table(rows=1, cols=2)
            table.style = 'Light Grid Accent 1'
            header_cells = table.rows[0].cells
            header_cells[0].text = 'Name'
            header_cells[1].text = 'Title/Position'

            for person in report.persons_met.all():
                row_cells = table.add_row().cells
                row_cells[0].text = person.name or ''
                row_cells[1].text = person.title or ''
        else:
            doc.add_paragraph('No persons met recorded.')
        
        # Services Provided
        doc.add_heading('Services Provided', level=1)
        if report.services_provided.exists():
            table = doc.add_table(rows=1, cols=4)
            table.style = 'Light Grid Accent 1'
            header_cells = table.rows[0].cells
            header_cells[0].text = 'Service'
            header_cells[1].text = 'Indicator'
            header_cells[2].text = 'Findings'
            header_cells[3].text = 'Recommended Action'
            
            for service in report.services_provided.all():
                row_cells = table.add_row().cells
                row_cells[0].text = service.service_name or ''
                row_cells[1].text = service.indicator.code if service.indicator else ''
                row_cells[2].text = service.findings or ''
                row_cells[3].text = service.recommended_action or ''
        else:
            doc.add_paragraph('No services recorded.')
        
        # Challenges
        doc.add_heading('Challenges Identified', level=1)
        if report.challenges.exists():
            for challenge in report.challenges.all():
                para = doc.add_paragraph()
                para.add_run(f'Priority: {challenge.get_priority_display()}\n').bold = True
                para.add_run(f'Challenge: {challenge.challenge_description}\n')
                para.add_run(f'Recommendation: {challenge.recommendation}')
                doc.add_paragraph()  # Spacing
        else:
            doc.add_paragraph('No challenges recorded.')
        
        # Best Practices
        doc.add_heading('Best Practices', level=1)
        if report.best_practices.exists():
            for practice in report.best_practices.all():
                para = doc.add_paragraph()
                para.add_run(f'Practice: {practice.practice_description}\n')
                para.add_run(f'Replicable: {"Yes" if practice.replicable else "No"}\n')
                para.add_run(f'Lessons Learned: {practice.lessons_learned}')
                doc.add_paragraph()  # Spacing
        else:
            doc.add_paragraph('No best practices recorded.')
        
        # Create response
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        response['Content-Disposition'] = f'attachment; filename="FVR-{report.report_code}.docx"'
        doc.save(response)
        
        return response
    
    except Exception as e:
        messages.error(request, f'Error exporting report: {str(e)}')
        return redirect('field_monitoring:field_visit_detail', pk=report.id)


# ============================================
# DASHBOARD / ANALYTICS
# ============================================

@login_required
def field_monitoring_dashboard(request):
    """Field monitoring analytics dashboard"""
    user = request.user
    
    # Base queryset scoped to what this user is allowed to see
    reports = _get_visible_reports(user)
    
    # Statistics
    total_reports = reports.count()
    approved_reports = reports.filter(status='approved').count()
    pending_reports = reports.filter(status='submitted').count()
    recent_reports = reports.order_by('-visit_date')[:10]
    
    # Challenges statistics
    from django.db.models import Count
    total_challenges = Challenge.objects.filter(visit__in=reports).count()
    critical_challenges = Challenge.objects.filter(
        visit__in=reports,
        priority='critical'
    ).count()
    
    # Best practices
    replicable_practices = BestPractice.objects.filter(
        visit__in=reports,
        replicable=True
    ).count()
    
    # County statistics (if admin/approver)
    county_stats = None
    if _can_view_all_reports(user):
        county_stats = reports.values('county__name').annotate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='approved'))
        ).order_by('-total')[:10]
    
    context = {
        'total_reports': total_reports,
        'approved_reports': approved_reports,
        'pending_reports': pending_reports,
        'total_challenges': total_challenges,
        'critical_challenges': critical_challenges,
        'replicable_practices': replicable_practices,
        'recent_reports': recent_reports,
        'county_stats': county_stats,
    }
    
    return render(request, 'field_monitoring/dashboard.html', context)
