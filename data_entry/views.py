from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError
from django.utils import timezone
from django.db.models import Q
from core.models import County, Quarter
from indicators.models import Indicator
from .models import DataEntry
from users.decorators import view_reports_required, ncpd_or_admin_required


@login_required
def data_entry_list(request):
    """List data entries - RBAC: County users only see their county"""
    user = request.user
    
    # ===== RBAC: COUNTY USERS ONLY SEE THEIR COUNTY =====
    if user.role and user.role.name == 'county_me' and user.county:
        entries = DataEntry.objects.filter(county=user.county).order_by('-created_at')
        county_name = user.county.name
    elif user.is_superuser or (user.role and user.role.name in ['admin', 'ncpd_me']):
        entries = DataEntry.objects.all().order_by('-created_at')
        county_name = None
    else:
        entries = DataEntry.objects.none()
        county_name = None
    
    # Counts for summary
    total = entries.count()
    drafts = entries.filter(status='draft').count()
    submitted = entries.filter(status='submitted').count()
    approved = entries.filter(status='approved').count()
    rejected = entries.filter(status='rejected').count()
    
    # Debug - print to console
    for entry in entries[:5]:
        print(f"Entry {entry.id}: submitted_by={entry.submitted_by}, submitted_at={entry.submitted_at}")
    
    context = {
        'entries': entries,
        'total': total,
        'drafts': drafts,
        'submitted': submitted,
        'approved': approved,
        'rejected': rejected,
        'is_county_user': user.role and user.role.name == 'county_me',
        'county_name': county_name,
        'user_role': user.role.name if user.role else 'No Role',
    }
    return render(request, 'data_entry/list.html', context)

@login_required
def data_entry_form(request):
    """Data entry form - RBAC: County users auto-assigned to their county"""
    user = request.user
    
    # Only show active quarters
    quarters = Quarter.objects.filter(is_active=True, is_closed=False)
    
    # Show all active indicators
    indicators = Indicator.objects.filter(is_active=True)
    
    # ===== RBAC: COUNTY USERS ONLY SEE THEIR COUNTY =====
    if user.role and user.role.name == 'county_me' and user.county:
        counties = County.objects.filter(id=user.county.id)
        default_county = user.county
        is_county_user = True
    elif user.is_superuser or (user.role and user.role.name in ['admin', 'ncpd_me']):
        counties = County.objects.filter(is_active=True)
        default_county = None
        is_county_user = False
    else:
        counties = County.objects.none()
        default_county = None
        is_county_user = False
    
    # Get existing data for pre-filling with status
    existing_data = {}
    existing_status = {}
    if request.method == 'GET':
        county_id = request.GET.get('county')
        quarter_id = request.GET.get('quarter')
        
        if county_id and quarter_id:
            try:
                county = County.objects.get(id=county_id)
                quarter = Quarter.objects.get(id=quarter_id)
                
                # Check if user can view this county
                if is_county_user and county.id != user.county.id:
                    pass
                else:
                    entries = DataEntry.objects.filter(
                        county=county,
                        quarter=quarter
                    )
                    for entry in entries:
                        existing_data[entry.indicator_id] = entry.value
                        existing_status[entry.indicator_id] = entry.status
            except (County.DoesNotExist, Quarter.DoesNotExist):
                pass
    
    if request.method == 'POST':
        action = request.POST.get('action', 'draft')
        county_id = request.POST.get('county')
        quarter_id = request.POST.get('quarter')
        
        if not county_id or not quarter_id:
            messages.error(request, 'Please select both county and quarter.')
            return render(request, 'data_entry/form.html', {
                'counties': counties,
                'quarters': quarters,
                'indicators': indicators,
                'default_county': default_county,
                'is_county_user': is_county_user,
                'existing_data': existing_data,
                'existing_status': existing_status,
            })
        
        county = get_object_or_404(County, id=county_id)
        quarter = get_object_or_404(Quarter, id=quarter_id)
        
        # ===== RBAC: VERIFY COUNTY USER CAN ONLY SUBMIT FOR THEIR COUNTY =====
        if user.role and user.role.name == 'county_me' and user.county:
            if user.county.id != county.id:
                messages.error(request, 'You can only submit data for your assigned county.')
                return render(request, 'data_entry/form.html', {
                    'counties': counties,
                    'quarters': quarters,
                    'indicators': indicators,
                    'default_county': default_county,
                    'is_county_user': is_county_user,
                    'existing_data': existing_data,
                    'existing_status': existing_status,
                })
        
        saved_count = 0
        error_count = 0
        error_messages = []
        blocked_count = 0
        
        for indicator in indicators:
            value = request.POST.get(f'indicator_{indicator.id}', '').strip()
            
            # Skip if no value entered
            if not value:
                continue
            
            # Validate the value against indicator rules
            is_valid, error_message = indicator.validate_value(value)
            if not is_valid:
                error_count += 1
                error_messages.append(f"{indicator.code}: {error_message}")
                continue
            
            # Check if entry already exists
            existing = DataEntry.objects.filter(
                county=county,
                quarter=quarter,
                indicator=indicator
            ).first()
            
            # ===== CRITICAL: BLOCK IF APPROVED OR SUBMITTED =====
            if existing and existing.status in ['approved', 'submitted']:
                blocked_count += 1
                error_messages.append(f"{indicator.code}: Already {existing.status} and cannot be modified")
                continue
            
            try:
                if existing:
                    # Update existing (draft or rejected)
                    existing.value = value
                    
                    if action == 'draft':
                        existing.status = 'draft'
                        existing.submitted_at = None  # Clear submitted_at for draft
                    else:
                        existing.status = 'submitted'
                        existing.submitted_by = user
                        existing.submitted_at = timezone.now()  # <-- SET THIS
                        existing.rejection_reason = ''
                    
                    existing.save()
                    saved_count += 1
                else:
                    # Create new
                    entry = DataEntry(
                        county=county,
                        quarter=quarter,
                        indicator=indicator,
                        value=value,
                        target_at_submission=indicator.target_value,
                    )
                    
                    if action == 'draft':
                        entry.status = 'draft'
                        entry.submitted_by = user
                        entry.submitted_at = None
                    else:
                        entry.status = 'submitted'
                        entry.submitted_by = user
                        entry.submitted_at = timezone.now()  # <-- SET THIS
                    
                    entry.save()
                    saved_count += 1
            except IntegrityError:
                error_count += 1
                error_messages.append(f"Duplicate entry for {indicator.code}")
            except Exception as e:
                error_count += 1
                error_messages.append(f"Error for {indicator.code}: {str(e)}")
        
        if blocked_count > 0:
            messages.error(request, f'{blocked_count} indicator(s) are already submitted or approved and cannot be modified.')
        
        if error_messages:
            for msg in error_messages[:5]:
                messages.error(request, msg)
        
        if saved_count == 0 and error_count == 0 and blocked_count == 0:
            messages.warning(request, 'No data was saved. Please fill in at least one indicator value.')
        elif saved_count > 0 and action == 'draft':
            messages.success(request, f'Draft saved successfully! ({saved_count} entries)')
        elif saved_count > 0 and action == 'submitted':
            # Send notifications
            try:
                from notifications.utils import notify_submission
                submitted_entries = DataEntry.objects.filter(
                    county=county,
                    quarter=quarter,
                    status='submitted',
                    submitted_by=user
                )
                for entry in submitted_entries:
                    notify_submission(entry, user)
            except ImportError:
                pass
            
            messages.success(request, f'Submitted for approval! ({saved_count} entries)')
            return redirect('data_entry:pending')
        
        return redirect('data_entry:list')
    
    context = {
        'counties': counties,
        'quarters': quarters,
        'indicators': indicators,
        'default_county': default_county,
        'is_county_user': is_county_user,
        'existing_data': existing_data,
        'existing_status': existing_status,
        'user_role': user.role.name if user.role else 'No Role',
    }
    return render(request, 'data_entry/form.html', context)

@login_required
def data_entry_edit(request, pk):
    """Edit a data entry - RBAC: County users can only edit their county entries"""
    entry = get_object_or_404(DataEntry, pk=pk)
    user = request.user
    
    # ===== CHECK IF ENTRY IS APPROVED OR SUBMITTED =====
    if entry.status in ['approved', 'submitted']:
        messages.error(request, f'{entry.get_status_display()} entries cannot be edited.')
        return redirect('data_entry:list')
    
    # ===== RBAC: CHECK PERMISSION TO EDIT =====
    if not entry.can_edit(user):
        messages.error(request, 'You do not have permission to edit this entry.')
        return redirect('data_entry:list')
    
    if request.method == 'POST':
        value = request.POST.get('value', '').strip()
        
        if not value:
            messages.error(request, 'Please enter a value.')
            return render(request, 'data_entry/edit.html', {'entry': entry})
        
        # Validate the value
        is_valid, error_message = entry.indicator.validate_value(value)
        if not is_valid:
            messages.error(request, error_message)
            return render(request, 'data_entry/edit.html', {'entry': entry})
        
        try:
            entry.value = value
            entry.rejection_reason = ''  # Clear rejection reason
            
            # Check if user wants to submit
            if 'submit' in request.POST or 'resubmit' in request.POST:
                entry.status = 'submitted'
                entry.submitted_by = user
                entry.submitted_at = timezone.now()  # <-- SET THIS
                entry.target_at_submission = entry.indicator.target_value
                entry.save()
                
                # Send notification
                try:
                    from notifications.utils import notify_submission
                    notify_submission(entry, user)
                except ImportError:
                    pass
                
                messages.success(request, f'Entry for {entry.indicator.code} submitted for approval.')
                return redirect('data_entry:pending')
            else:
                # Just update as draft
                entry.status = 'draft'
                entry.submitted_at = None  # Clear submitted_at for draft
                entry.save()
                messages.success(request, f'Entry for {entry.indicator.code} updated successfully.')
                return redirect('data_entry:list')
            
        except Exception as e:
            messages.error(request, f'Error saving: {str(e)}')
            return render(request, 'data_entry/edit.html', {'entry': entry})
    
    context = {
        'entry': entry,
        'is_county_user': user.role and user.role.name == 'county_me',
    }
    return render(request, 'data_entry/edit.html', context)

@login_required
def data_entry_submit(request, pk):
    """Submit a data entry for approval - RBAC enforced"""
    entry = get_object_or_404(DataEntry, pk=pk)
    user = request.user
    
    # ===== CHECK IF ENTRY IS APPROVED OR ALREADY SUBMITTED =====
    if entry.status == 'approved':
        messages.error(request, 'Approved entries cannot be resubmitted.')
        return redirect('data_entry:list')
    
    if entry.status == 'submitted':
        messages.error(request, 'This entry is already submitted and pending approval.')
        return redirect('data_entry:list')
    
    if not entry.can_edit(user):
        messages.error(request, 'You cannot submit this entry.')
        return redirect('data_entry:list')
    
    if not entry.value:
        messages.error(request, 'Cannot submit empty entry. Please add a value first.')
        return redirect('data_entry:edit', pk=entry.pk)
    
    # Validate the value before submitting
    is_valid, error_message = entry.indicator.validate_value(entry.value)
    if not is_valid:
        messages.error(request, f'Cannot submit: {error_message}')
        return redirect('data_entry:edit', pk=entry.pk)
    
    entry.status = 'submitted'
    entry.submitted_by = user
    entry.submitted_at = timezone.now()  # <-- SET THIS
    entry.target_at_submission = entry.indicator.target_value
    entry.rejection_reason = ''
    entry.save()
    
    # Send notifications
    try:
        from notifications.utils import notify_submission
        notify_submission(entry, user)
    except ImportError:
        pass
    
    messages.success(request, f'Entry for {entry.indicator.code} submitted for approval.')
    return redirect('data_entry:list')

@login_required
@ncpd_or_admin_required
def data_entry_approve(request, pk):
    """Approve a data entry - NCPD/Admin only"""
    entry = get_object_or_404(DataEntry, pk=pk)
    user = request.user
    
    if not entry.can_approve(user):
        messages.error(request, 'You do not have permission to approve entries.')
        return redirect('data_entry:list')
    
    entry.status = 'approved'
    entry.approved_by = user
    entry.approved_at = timezone.now()
    entry.is_locked = True
    entry.save()
    
    # Send notification
    try:
        from notifications.utils import notify_approval
        notify_approval(entry, user)
    except ImportError:
        pass
    
    messages.success(request, f'Entry for {entry.indicator.code} approved.')
    return redirect('data_entry:pending')

@login_required
@ncpd_or_admin_required
def data_entry_reject(request, pk):
    """Reject a data entry with reason - NCPD/Admin only"""
    entry = get_object_or_404(DataEntry, pk=pk)
    user = request.user
    
    if not entry.can_approve(user):
        messages.error(request, 'You do not have permission to reject entries.')
        return redirect('data_entry:list')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, 'Please provide a reason for rejection.')
            return render(request, 'data_entry/reject.html', {'entry': entry})
        
        entry.status = 'rejected'
        entry.rejection_reason = reason
        entry.is_locked = False
        entry.save()
        
        # Send notification
        try:
            from notifications.utils import notify_rejection
            notify_rejection(entry, user, reason)
        except ImportError:
            pass
        
        messages.warning(request, f'Entry for {entry.indicator.code} rejected. Reason: {reason}')
        return redirect('data_entry:pending')
    
    return render(request, 'data_entry/reject.html', {'entry': entry})

@login_required
def data_entry_delete(request, pk):
    """Delete a data entry - RBAC enforced"""
    entry = get_object_or_404(DataEntry, pk=pk)
    user = request.user
    
    if entry.status == 'approved':
        messages.error(request, 'Cannot delete approved entries.')
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
@ncpd_or_admin_required
def pending_approvals(request):
    """View pending approvals - NCPD/Admin only"""
    if request.user.role and request.user.role.name not in ['admin', 'ncpd_me'] and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to view pending approvals.')
        return redirect('data_entry:list')
    
    pending = DataEntry.objects.filter(status='submitted').order_by('submitted_at')
    
    # ===== RBAC: COUNTY USERS ONLY SEE THEIR COUNTY (though they can't approve) =====
    # This is handled by the decorator above
    
    context = {
        'pending': pending,
        'total_pending': pending.count(),
    }
    return render(request, 'data_entry/pending.html', context)

@login_required
def data_entry_detail(request, pk):
    """View a single data entry detail - RBAC enforced"""
    entry = get_object_or_404(DataEntry, pk=pk)
    user = request.user
    
    # ===== RBAC: COUNTY USERS ONLY SEE THEIR COUNTY =====
    if user.role and user.role.name == 'county_me' and user.county:
        if entry.county.id != user.county.id:
            messages.error(request, 'You do not have permission to view this entry.')
            return redirect('data_entry:list')
    
    context = {
        'entry': entry,
        'is_county_user': user.role and user.role.name == 'county_me',
    }
    return render(request, 'data_entry/detail.html', context)
    
def get_submitted_by_display(self):
    """Get display name of who submitted this entry"""
    if self.submitted_by:
        return self.submitted_by.get_full_name() or self.submitted_by.username
    return '—'
