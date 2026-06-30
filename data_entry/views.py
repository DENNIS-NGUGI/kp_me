from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from core.models import County, Quarter
from indicators.models import Indicator, ThematicArea
from .models import DataEntry
from users.decorators import permission_required, module_permission_required
from users.permissions import get_data_entry_queryset_filter
from notifications.utils import notify_submission, notify_approval, notify_rejection


@login_required
@module_permission_required('data_entry', 'view')
def data_entry_list(request):
    """List data entries - FULLY DATABASE DRIVEN"""
    user = request.user
    
    # Use the centralized filter for permissions
    entries = DataEntry.objects.filter(get_data_entry_queryset_filter(user))
    
    # Apply additional filters
    status_filter = request.GET.get('status')
    county_filter = request.GET.get('county')
    quarter_filter = request.GET.get('quarter')
    indicator_filter = request.GET.get('indicator')
    search_query = request.GET.get('search')
    
    if status_filter:
        entries = entries.filter(status=status_filter)
    if county_filter:
        # Only apply county filter if user has permission
        if user.is_superuser or user.has_permission('can_approve_data'):
            entries = entries.filter(county_id=county_filter)
        elif user.is_county_user and int(county_filter) == user.county.id:
            entries = entries.filter(county_id=county_filter)
    if quarter_filter:
        entries = entries.filter(quarter_id=quarter_filter)
    if indicator_filter:
        entries = entries.filter(indicator_id=indicator_filter)
    if search_query:
        entries = entries.filter(
            Q(indicator__code__icontains=search_query) |
            Q(indicator__name__icontains=search_query) |
            Q(county__name__icontains=search_query)
        )
    
    entries = entries.select_related('county', 'quarter', 'indicator', 'submitted_by', 'approved_by')
    entries = entries.order_by('-created_at')
    
    # Summary counts
    total = entries.count()
    drafts = entries.filter(status='draft').count()
    submitted = entries.filter(status='submitted').count()
    approved = entries.filter(status='approved').count()
    rejected = entries.filter(status='rejected').count()
    
    # For filters dropdown
    counties = County.objects.filter(is_active=True)
    quarters = Quarter.objects.filter(is_active=True)
    indicators = Indicator.objects.filter(is_active=True)
    
    if user.is_county_user:
        counties = counties.filter(id=user.county.id)
    
    can_add = user.has_module_permission('data_entry', 'add')
    can_approve = user.has_permission('can_approve_data')
    
    context = {
        'entries': entries,
        'total': total,
        'drafts': drafts,
        'submitted': submitted,
        'approved': approved,
        'rejected': rejected,
        'counties': counties,
        'quarters': quarters,
        'indicators': indicators,
        'is_county_user': user.is_county_user,
        'county_name': user.county.name if user.is_county_user else None,
        'can_add': can_add,
        'can_approve': can_approve,
        'filters': {
            'status': status_filter,
            'county': county_filter,
            'quarter': quarter_filter,
            'indicator': indicator_filter,
            'search': search_query,
        }
    }
    return render(request, 'data_entry/list.html', context)

@login_required
@module_permission_required('data_entry', 'add')
def data_entry_form(request):
    """Simple data entry form - No review step"""
    user = request.user
    
    # Get parameters
    county_id = request.GET.get('county')
    quarter_id = request.GET.get('quarter')
    step = request.GET.get('step', '1')
    
    # County user auto-select
    is_county_user = user.county is not None
    if is_county_user and not county_id:
        county_id = str(user.county.id)
    
    # Get data
    counties = County.objects.filter(id=user.county.id) if is_county_user else County.objects.filter(is_active=True)
    quarters = Quarter.objects.filter(is_active=True, is_closed=False)
    indicators = Indicator.objects.filter(is_active=True)
    
    # Get existing data
    existing_data = {}
    existing_status = {}
    selected_county = None
    selected_quarter = None
    
    if county_id and quarter_id:
        selected_county = get_object_or_404(County, id=county_id)
        selected_quarter = get_object_or_404(Quarter, id=quarter_id)
        
        entries = DataEntry.objects.filter(county=selected_county, quarter=selected_quarter)
        for entry in entries:
            existing_data[entry.indicator_id] = entry.value
            existing_status[entry.indicator_id] = entry.status
    
    # Group indicators
    from indicators.models import ThematicArea
    areas = ThematicArea.objects.filter(
        id__in=indicators.values_list('thematic_area_id', flat=True).distinct()
    )
    for area in areas:
        area.indicator_list = indicators.filter(thematic_area=area)
    
    # Get selected indicators
    selected_ids = request.GET.get('selected', '')
    selected_indicators = [int(x) for x in selected_ids.split(',') if x.isdigit()] if selected_ids else []
    
    # ===== PROCESS POST =====
    if request.method == 'POST':
        action = request.POST.get('action')
        county_id = request.POST.get('county')
        quarter_id = request.POST.get('quarter')
        selected_indicators = request.POST.getlist('selected_indicators')
        
        # Step 2 -> Step 3
        if 'go_to_data_entry' in request.POST:
            if not selected_indicators:
                messages.error(request, 'Please select at least one indicator.')
                return redirect(f'{request.path}?step=2&county={county_id}&quarter={quarter_id}')
            
            selected_str = ','.join(selected_indicators)
            return redirect(f'{request.path}?step=3&county={county_id}&quarter={quarter_id}&selected={selected_str}')
        
        # Step 3 -> Submit or Save Draft
        if action in ['submit', 'draft']:
            if not selected_indicators:
                messages.error(request, 'No indicators selected.')
                return redirect(f'{request.path}?step=2&county={county_id}&quarter={quarter_id}')
            
            county = get_object_or_404(County, id=county_id)
            quarter = get_object_or_404(Quarter, id=quarter_id)
            
            saved = 0
            errors = []
            submitted_entries = []
            
            for indicator_id in selected_indicators:
                indicator = get_object_or_404(Indicator, id=indicator_id)
                value = request.POST.get(f'indicator_{indicator_id}', '').strip()
                
                # Skip empty values for draft
                if not value:
                    if action == 'submit':
                        errors.append(f"{indicator.code}: No value")
                    continue
                
                is_valid, err = indicator.validate_value(value)
                if not is_valid:
                    errors.append(f"{indicator.code}: {err}")
                    continue
                
                existing = DataEntry.objects.filter(
                    county=county, quarter=quarter, indicator=indicator
                ).first()
                
                if existing and existing.status in ['approved', 'submitted']:
                    continue
                
                try:
                    if existing:
                        existing.value = value
                        existing.status = 'submitted' if action == 'submit' else 'draft'
                        existing.notes = request.POST.get(f'notes_{indicator_id}', '')
                        
                        if action == 'submit':
                            existing.submitted_by = user
                            existing.submitted_at = timezone.now()
                            existing.target_at_submission = indicator.target_value
                            submitted_entries.append(existing)
                        else:
                            if existing.status == 'draft':
                                existing.submitted_by = None
                                existing.submitted_at = None
                        existing.save()
                    else:
                        entry = DataEntry(
                            county=county,
                            quarter=quarter,
                            indicator=indicator,
                            value=value,
                            status='submitted' if action == 'submit' else 'draft',
                            notes=request.POST.get(f'notes_{indicator_id}', ''),
                            target_at_submission=indicator.target_value if action == 'submit' else None,
                            submitted_by=user if action == 'submit' else None,
                            submitted_at=timezone.now() if action == 'submit' else None,
                        )
                        entry.save()
                        if action == 'submit':
                            submitted_entries.append(entry)
                    saved += 1
                except Exception as e:
                    errors.append(f"{indicator.code}: {str(e)}")
            
            # Send notifications for submitted entries
            if action == 'submit' and submitted_entries:
                for entry in submitted_entries:
                    notify_submission(entry, user)
            
            if errors:
                for err in errors[:3]:
                    messages.error(request, err)
            
            if saved == 0 and action == 'submit':
                messages.error(request, 'No data submitted. Please enter values.')
            elif saved == 0:
                messages.warning(request, 'No data saved. Please enter values.')
            elif action == 'draft':
                messages.success(request, f'Draft saved! ({saved} entries)')
            else:
                messages.success(request, f'Submitted for approval! ({saved} entries)')
                return redirect('data_entry:list')
            
            return redirect('data_entry:list')
    
    context = {
        'counties': counties,
        'quarters': quarters,
        'areas': areas,
        'default_county': user.county if is_county_user else None,
        'is_county_user': is_county_user,
        'existing_data': existing_data,
        'existing_status': existing_status,
        'selected_county': selected_county,
        'selected_quarter': selected_quarter,
        'county_id': county_id,
        'quarter_id': quarter_id,
        'step': step,
        'selected_indicators': selected_indicators,
        'indicators': indicators,
    }
    return render(request, 'data_entry/form.html', context)

@login_required
@module_permission_required('data_entry', 'change')
def data_entry_submit(request, pk):
    """Submit a single data entry for approval"""
    entry = get_object_or_404(DataEntry, pk=pk)
    user = request.user
    
    # Check if user can submit
    if not entry.can_submit(user):
        messages.error(request, 'This entry cannot be submitted.')
        return redirect('data_entry:list')
    
    # Check if entry has a value
    if not entry.value:
        messages.error(request, 'Cannot submit empty entry. Please add a value first.')
        return redirect('data_entry:edit', pk=entry.pk)
    
    # Validate the value
    is_valid, error_message = entry.indicator.validate_value(entry.value)
    if not is_valid:
        messages.error(request, f'Cannot submit: {error_message}')
        return redirect('data_entry:edit', pk=entry.pk)
    
    # Update entry status
    entry.status = 'submitted'
    entry.submitted_by = user
    entry.submitted_at = timezone.now()
    entry.target_at_submission = entry.indicator.target_value
    entry.rejection_reason = ''
    entry.save()
    
    # Send notification
    notify_submission(entry, user)
    
    messages.success(request, f'Entry for {entry.indicator.code} submitted for approval.')
    return redirect('data_entry:list')

@login_required
@module_permission_required('data_entry', 'change')
def data_entry_edit(request, pk):
    """Edit a single data entry"""
    entry = get_object_or_404(DataEntry, pk=pk)
    user = request.user
    
    if not entry.can_edit(user):
        messages.error(request, 'You do not have permission to edit this entry.')
        return redirect('data_entry:list')
    
    if request.method == 'POST':
        value = request.POST.get('value', '').strip()
        action = request.POST.get('action', 'draft')
        
        if not value:
            messages.error(request, 'Please enter a value.')
            return render(request, 'data_entry/edit.html', {'entry': entry})
        
        is_valid, error_message = entry.indicator.validate_value(value)
        if not is_valid:
            messages.error(request, error_message)
            return render(request, 'data_entry/edit.html', {'entry': entry})
        
        try:
            entry.value = value
            entry.rejection_reason = ''
            
            if action == 'submit':
                entry.status = 'submitted'
                entry.submitted_by = user
                entry.submitted_at = timezone.now()
                entry.target_at_submission = entry.indicator.target_value
                entry.save()
                messages.success(request, f'Entry for {entry.indicator.code} submitted for approval.')
            else:
                entry.status = 'draft'
                entry.submitted_at = None
                entry.save()
                messages.success(request, f'Entry for {entry.indicator.code} updated successfully.')
            
            return redirect('data_entry:list')
        except Exception as e:
            messages.error(request, f'Error saving: {str(e)}')
    
    context = {
        'entry': entry,
        'can_submit': entry.can_submit(user),
    }
    return render(request, 'data_entry/edit.html', context)

@login_required
@module_permission_required('data_entry', 'delete')
def data_entry_delete(request, pk):
    """Delete a data entry"""
    entry = get_object_or_404(DataEntry, pk=pk)
    user = request.user
    
    if entry.status == 'approved':
        messages.error(request, 'Cannot delete approved entries.')
        return redirect('data_entry:list')
    
    if entry.status == 'submitted':
        messages.error(request, 'Cannot delete submitted entries. Please reject first.')
        return redirect('data_entry:list')
    
    if not entry.can_edit(user):
        messages.error(request, 'You cannot delete this entry.')
        return redirect('data_entry:list')
    
    if request.method == 'POST':
        entry.delete()
        messages.success(request, 'Entry deleted successfully.')
        return redirect('data_entry:list')
    
    context = {'entry': entry}
    return render(request, 'data_entry/confirm_delete.html', context)

@login_required
@permission_required('can_approve_data')
def data_entry_approve(request, pk):
    """Approve a data entry"""
    entry = get_object_or_404(DataEntry, pk=pk)
    user = request.user
    
    # Check if user can approve
    if not entry.can_approve(user):
        messages.error(request, 'You do not have permission to approve entries.')
        return redirect('data_entry:list')
    
    # Check if entry is submitted
    if entry.status != 'submitted':
        messages.error(request, 'Only submitted entries can be approved.')
        return redirect('data_entry:list')
    
    if request.method == 'POST':
        # Update entry
        entry.status = 'approved'
        entry.approved_by = user
        entry.approved_at = timezone.now()
        entry.is_locked = True
        entry.save()
        
        # Send notification
        notify_approval(entry, user)
        
        messages.success(request, f'Entry for {entry.indicator.code} approved.')
        return redirect('data_entry:pending')
    
    context = {'entry': entry}
    return render(request, 'data_entry/approve.html', context)

@login_required
@permission_required('can_approve_data')
def data_entry_reject(request, pk):
    """Reject a data entry with reason"""
    entry = get_object_or_404(DataEntry, pk=pk)
    user = request.user
    
    # Check if user can approve (reject)
    if not entry.can_approve(user):
        messages.error(request, 'You do not have permission to reject entries.')
        return redirect('data_entry:list')
    
    # Check if entry is submitted
    if entry.status != 'submitted':
        messages.error(request, 'Only submitted entries can be rejected.')
        return redirect('data_entry:list')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, 'Please provide a reason for rejection.')
            return render(request, 'data_entry/reject.html', {'entry': entry})
        
        # Update entry
        entry.status = 'rejected'
        entry.rejection_reason = reason
        entry.is_locked = False
        entry.save()
        
        # Send notification
        notify_rejection(entry, user, reason)
        
        messages.warning(request, f'Entry for {entry.indicator.code} rejected.')
        return redirect('data_entry:pending')
    
    context = {'entry': entry}
    return render(request, 'data_entry/reject.html', context)

@login_required
@permission_required('can_approve_data')
def pending_approvals(request):
    """View pending approvals"""
    user = request.user
    
    pending = DataEntry.objects.filter(status='submitted').select_related(
        'county', 'quarter', 'indicator', 'submitted_by'
    ).order_by('submitted_at')
    
    if user.is_county_user:
        pending = pending.filter(county=user.county)
    
    context = {
        'pending': pending,
        'total_pending': pending.count(),
    }
    return render(request, 'data_entry/pending.html', context)

@login_required
@module_permission_required('data_entry', 'view')
def data_entry_detail(request, pk):
    """View a single data entry detail"""
    entry = get_object_or_404(DataEntry, pk=pk)
    user = request.user
    
    if user.is_county_user and entry.county.id != user.county.id:
        if not user.has_permission('can_approve_data'):
            messages.error(request, 'You do not have permission to view this entry.')
            return redirect('data_entry:list')
    
    context = {
        'entry': entry,
        'can_edit': entry.can_edit(user),
        'can_approve': entry.can_approve(user),
        'can_submit': entry.can_submit(user),
    }
    return render(request, 'data_entry/detail.html', context)

@login_required
def data_entry_detail_api(request, pk):
    """API endpoint for entry details - Used by AJAX modal"""
    try:
        entry = get_object_or_404(DataEntry, pk=pk)
        user = request.user
        
        if user.is_county_user and entry.county.id != user.county.id:
            if not user.has_permission('can_approve_data'):
                return JsonResponse({
                    'error': 'Permission denied',
                    'message': 'You do not have permission to view this entry'
                }, status=403)
        
        data = {
            'id': entry.id,
            'county': entry.county.name if entry.county else '',
            'quarter': entry.quarter.name if entry.quarter else '',
            'indicator_code': entry.indicator.code if entry.indicator else '',
            'indicator_name': entry.indicator.name if entry.indicator else '',
            'thematic_area': entry.indicator.thematic_area.name if entry.indicator and entry.indicator.thematic_area else '',
            'indicator_type': entry.indicator.get_indicator_type_display() if entry.indicator else '',
            'value': entry.value or '',
            'status': entry.status,
            'status_display': entry.get_status_display(),
            'is_locked': entry.is_locked,
            'target_at_submission': str(entry.target_at_submission) if entry.target_at_submission else None,
            'submitted_by': entry.submitted_by.get_full_name() or entry.submitted_by.username if entry.submitted_by else None,
            'submitted_at': entry.submitted_at.strftime('%B %d, %Y %H:%M') if entry.submitted_at else None,
            'approved_by': entry.approved_by.get_full_name() or entry.approved_by.username if entry.approved_by else None,
            'approved_at': entry.approved_at.strftime('%B %d, %Y %H:%M') if entry.approved_at else None,
            'rejection_reason': entry.rejection_reason or '',
            'notes': entry.notes or '',
            'created_at': entry.created_at.strftime('%B %d, %Y %H:%M') if entry.created_at else None,
            'updated_at': entry.updated_at.strftime('%B %d, %Y %H:%M') if entry.updated_at else None,
        }
        
        return JsonResponse(data)
        
    except DataEntry.DoesNotExist:
        return JsonResponse({
            'error': 'Not found',
            'message': 'Entry not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'error': 'Server error',
            'message': str(e)
        }, status=500)

@login_required
def data_entry_submit_bulk(request):
    """Submit multiple entries for approval"""
    user = request.user
    
    if request.method != 'POST':
        return redirect('data_entry:list')
    
    entry_ids = request.POST.getlist('entry_ids')
    if not entry_ids:
        messages.error(request, 'No entries selected for submission.')
        return redirect('data_entry:list')
    
    submitted_count = 0
    error_count = 0
    
    for entry_id in entry_ids:
        try:
            entry = DataEntry.objects.get(pk=entry_id)
            if entry.can_submit(user) and entry.value:
                entry.status = 'submitted'
                entry.submitted_by = user
                entry.submitted_at = timezone.now()
                entry.target_at_submission = entry.indicator.target_value
                entry.save()
                submitted_count += 1
            else:
                error_count += 1
        except DataEntry.DoesNotExist:
            error_count += 1
    
    if submitted_count > 0:
        messages.success(request, f'{submitted_count} entries submitted for approval.')
    if error_count > 0:
        messages.warning(request, f'{error_count} entries could not be submitted.')
    
    return redirect('data_entry:list')