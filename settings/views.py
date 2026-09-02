from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q
from .models import SystemSetting
from core.models import Quarter, County
from django.utils import timezone
from datetime import datetime
from users.models import AuditLog
from users.decorators import permission_required, module_permission_required
import csv
import io


# ===== SYSTEM SETTINGS VIEWS =====

@login_required
@permission_required('can_manage_system_settings')
def settings_index(request):
    """System settings dashboard"""
    settings = SystemSetting.objects.filter(is_editable=True)
    
    # Group settings by category
    categories = {}
    for setting in settings:
        parts = setting.key.split('_')
        category = parts[0] if parts else 'General'
        if category not in categories:
            categories[category] = []
        categories[category].append(setting)
    
    context = {
        'categories': categories,
        'can_manage': request.user.has_permission('can_manage_system_settings'),
    }
    return render(request, 'settings/index.html', context)


@login_required
@permission_required('can_manage_system_settings')
def settings_edit(request, key):
    """Edit a system setting"""
    setting = get_object_or_404(SystemSetting, key=key)
    
    if request.method == 'POST':
        value = request.POST.get('value', '').strip()
        
        if setting.setting_type == 'boolean':
            value = request.POST.get('value', 'false')
        
        old_value = setting.value
        setting.value = value
        setting.updated_by = request.user
        setting.save()
        
        # Use centralized audit log
        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.UPDATE,
            model_instance=setting,
            request=request,
            changes={
                'value': {'old': old_value, 'new': value}
            }
        )
        
        messages.success(request, f'Setting "{setting.key}" updated successfully!')
        return redirect('settings:index')
    
    context = {'setting': setting}
    return render(request, 'settings/edit.html', context)


@login_required
@permission_required('can_manage_system_settings')
def settings_add(request):
    """Add a new system setting"""
    if request.method == 'POST':
        key = request.POST.get('key', '').strip()
        value = request.POST.get('value', '').strip()
        setting_type = request.POST.get('setting_type', 'string')
        description = request.POST.get('description', '')
        is_editable = request.POST.get('is_editable') == 'on'
        is_public = request.POST.get('is_public') == 'on'
        
        if SystemSetting.objects.filter(key=key).exists():
            messages.error(request, f'Setting "{key}" already exists.')
            return redirect('settings:add')
        
        setting = SystemSetting.objects.create(
            key=key,
            value=value,
            setting_type=setting_type,
            description=description,
            is_editable=is_editable,
            is_public=is_public,
            updated_by=request.user
        )
        
        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.CREATE,
            model_instance=setting,
            request=request
        )
        
        messages.success(request, f'Setting "{key}" created successfully!')
        return redirect('settings:index')
    
    context = {
        'setting_types': SystemSetting.SETTING_TYPES,
    }
    return render(request, 'settings/add.html', context)


@login_required
@permission_required('can_manage_system_settings')
def settings_delete(request, key):
    """Delete a system setting"""
    setting = get_object_or_404(SystemSetting, key=key)
    
    if request.method == 'POST':
        setting.delete()
        
        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.DELETE,
            model_instance=setting,
            request=request
        )
        
        messages.success(request, f'Setting "{key}" deleted successfully!')
        return redirect('settings:index')
    
    context = {'setting': setting}
    return render(request, 'settings/delete.html', context)


# ===== AUDIT LOG VIEW =====

@login_required
@permission_required('view_auditlog')
def audit_log(request):
    """View audit log"""
    logs = AuditLog.objects.select_related('user').all()
    
    # Apply filters
    action = request.GET.get('action')
    model = request.GET.get('model')
    user_id = request.GET.get('user')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if action:
        logs = logs.filter(action=action.upper())
    if model:
        logs = logs.filter(model_name=model)
    if user_id:
        logs = logs.filter(user_id=user_id)
    if date_from:
        logs = logs.filter(timestamp__date__gte=date_from)
    if date_to:
        logs = logs.filter(timestamp__date__lte=date_to)
    
    # Get filter options
    actions = AuditLog.objects.values_list('action', flat=True).distinct()
    models = AuditLog.objects.values_list('model_name', flat=True).distinct()
    users = AuditLog.objects.select_related('user').values_list('user__username', flat=True).distinct()
    
    context = {
        'logs': logs[:100],
        'actions': actions,
        'models': models,
        'users': users,
        'selected_action': action,
        'selected_model': model,
        'selected_user': user_id,
        'total': logs.count(),
        'can_manage': request.user.has_permission('can_manage_system_settings'),
    }
    return render(request, 'settings/audit_log.html', context)


# ===== QUARTER MANAGEMENT VIEWS =====

@login_required
@permission_required('can_manage_system_settings')
def quarter_management(request):
    """Manage reporting quarters"""
    quarters = Quarter.objects.all().order_by('-start_date')
    
    context = {
        'quarters': quarters,
        'can_manage': request.user.has_permission('can_manage_system_settings'),
    }
    return render(request, 'settings/quarters.html', context)


@login_required
@permission_required('can_manage_system_settings')
def quarter_add(request):
    """Add a new quarter"""
    if request.method == 'POST':
        try:
            quarter = Quarter.objects.create(
                name=request.POST.get('name'),
                fiscal_year=request.POST.get('fiscal_year'),
                quarter_number=request.POST.get('quarter_number'),
                start_date=request.POST.get('start_date'),
                end_date=request.POST.get('end_date'),
                submission_deadline=request.POST.get('submission_deadline'),
                is_active=request.POST.get('is_active') == 'on',
                is_closed=request.POST.get('is_closed') == 'on',
            )
            
            AuditLog.log(
                user=request.user,
                action=AuditLog.Action.CREATE,
                model_instance=quarter,
                request=request
            )
            
            messages.success(request, 'Quarter added successfully!')
            return redirect('settings:quarters')
        except Exception as e:
            messages.error(request, f'Error adding quarter: {str(e)}')
    
    return render(request, 'settings/quarter_form.html')


@login_required
@permission_required('can_manage_system_settings')
def quarter_edit(request, pk):
    """Edit a quarter"""
    quarter = get_object_or_404(Quarter, pk=pk)
    
    if request.method == 'POST':
        try:
            old_data = {
                'name': quarter.name,
                'is_active': quarter.is_active,
                'is_closed': quarter.is_closed,
            }
            
            quarter.name = request.POST.get('name')
            quarter.fiscal_year = request.POST.get('fiscal_year')
            quarter.quarter_number = request.POST.get('quarter_number')
            quarter.start_date = request.POST.get('start_date')
            quarter.end_date = request.POST.get('end_date')
            quarter.submission_deadline = request.POST.get('submission_deadline')
            quarter.is_active = request.POST.get('is_active') == 'on'
            quarter.is_closed = request.POST.get('is_closed') == 'on'
            quarter.save()
            
            AuditLog.log(
                user=request.user,
                action=AuditLog.Action.UPDATE,
                model_instance=quarter,
                request=request,
                changes=old_data
            )
            
            messages.success(request, 'Quarter updated successfully!')
            return redirect('settings:quarters')
        except Exception as e:
            messages.error(request, f'Error updating quarter: {str(e)}')
    
    context = {'quarter': quarter}
    return render(request, 'settings/quarter_form.html', context)


@login_required
@permission_required('can_manage_system_settings')
def quarter_toggle(request, pk):
    """Toggle quarter active status"""
    quarter = get_object_or_404(Quarter, pk=pk)
    quarter.is_active = not quarter.is_active
    quarter.save()
    
    status = 'activated' if quarter.is_active else 'deactivated'
    messages.success(request, f'Quarter "{quarter.name}" {status} successfully!')
    return redirect('settings:quarters')


@login_required
@permission_required('can_manage_system_settings')
def quarter_delete(request, pk):
    """Delete a quarter"""
    quarter = get_object_or_404(Quarter, pk=pk)
    
    # Check if quarter has data entries
    from data_entry.models import DataEntry
    if DataEntry.objects.filter(quarter=quarter).exists():
        messages.error(request, f'Cannot delete "{quarter.name}" - it has associated data entries.')
        return redirect('settings:quarters')
    
    if request.method == 'POST':
        quarter.delete()
        
        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.DELETE,
            model_instance=quarter,
            request=request
        )
        
        messages.success(request, 'Quarter deleted successfully!')
        return redirect('settings:quarters')
    
    context = {'quarter': quarter}
    return render(request, 'settings/quarter_delete.html', context)


# ===== COUNTY MANAGEMENT VIEWS =====

@login_required
@permission_required('can_manage_system_settings')
def county_management(request):
    """Manage counties"""
    counties = County.objects.all().order_by('code')
    
    region_stats = {}
    for county in counties:
        region = county.region
        if region not in region_stats:
            region_stats[region] = 0
        region_stats[region] += 1
    
    context = {
        'counties': counties,
        'region_stats': region_stats,
        'total_counties': counties.count(),
        'can_manage': request.user.has_permission('can_manage_system_settings'),
    }
    return render(request, 'settings/counties.html', context)


@login_required
@permission_required('can_manage_system_settings')
def county_add(request):
    """Add a new county"""
    if request.method == 'POST':
        try:
            county = County.objects.create(
                code=request.POST.get('code'),
                name=request.POST.get('name'),
                headquarters=request.POST.get('headquarters'),
                region=request.POST.get('region'),
                population=request.POST.get('population') or None,
                area_sq_km=request.POST.get('area_sq_km') or None,
                is_active=request.POST.get('is_active') == 'on',
            )
            
            AuditLog.log(
                user=request.user,
                action=AuditLog.Action.CREATE,
                model_instance=county,
                request=request
            )
            
            messages.success(request, 'County added successfully!')
            return redirect('settings:counties')
        except Exception as e:
            messages.error(request, f'Error adding county: {str(e)}')
    
    regions = County.REGION_CHOICES
    context = {'regions': regions}
    return render(request, 'settings/county_form.html', context)


@login_required
@permission_required('can_manage_system_settings')
def county_edit(request, pk):
    """Edit a county"""
    county = get_object_or_404(County, pk=pk)
    
    if request.method == 'POST':
        try:
            old_data = {
                'name': county.name,
                'code': county.code,
                'is_active': county.is_active,
            }
            
            county.code = request.POST.get('code')
            county.name = request.POST.get('name')
            county.headquarters = request.POST.get('headquarters')
            county.region = request.POST.get('region')
            county.population = request.POST.get('population') or None
            county.area_sq_km = request.POST.get('area_sq_km') or None
            county.is_active = request.POST.get('is_active') == 'on'
            county.save()
            
            AuditLog.log(
                user=request.user,
                action=AuditLog.Action.UPDATE,
                model_instance=county,
                request=request,
                changes=old_data
            )
            
            messages.success(request, f'County "{county.name}" updated successfully!')
            return redirect('settings:counties')
        except Exception as e:
            messages.error(request, f'Error updating county: {str(e)}')
    
    regions = County.REGION_CHOICES
    context = {'county': county, 'regions': regions}
    return render(request, 'settings/county_form.html', context)


@login_required
@permission_required('can_manage_system_settings')
def county_toggle(request, pk):
    """Toggle county active status"""
    county = get_object_or_404(County, pk=pk)
    county.is_active = not county.is_active
    county.save()
    
    status = 'activated' if county.is_active else 'deactivated'
    messages.success(request, f'County "{county.name}" {status} successfully!')
    return redirect('settings:counties')


@login_required
@permission_required('can_manage_system_settings')
def county_delete(request, pk):
    """Delete a county"""
    county = get_object_or_404(County, pk=pk)
    
    # Check if county has data entries
    from data_entry.models import DataEntry
    if DataEntry.objects.filter(county=county).exists():
        messages.error(request, f'Cannot delete "{county.name}" - it has associated data entries.')
        return redirect('settings:counties')
    
    if request.method == 'POST':
        county_name = county.name
        county.delete()
        
        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.DELETE,
            model_instance=county,
            request=request
        )
        
        messages.success(request, f'County "{county_name}" deleted successfully!')
        return redirect('settings:counties')
    
    context = {'county': county}
    return render(request, 'settings/county_delete.html', context)


@login_required
@permission_required('can_manage_system_settings')
def county_export(request):
    """Export counties to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="counties_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Code', 'Name', 'Headquarters', 'Region', 'Population', 'Area (sq km)', 'Active'])
    
    for county in County.objects.all().order_by('code'):
        writer.writerow([
            county.code,
            county.name,
            county.headquarters,
            county.get_region_display(),
            county.population or '',
            county.area_sq_km or '',
            'Yes' if county.is_active else 'No'
        ])
    
    return response


@login_required
@permission_required('can_manage_system_settings')
def county_import(request):
    """Import counties from CSV"""
    if request.method != 'POST':
        return redirect('settings:counties')
    
    if 'file' not in request.FILES:
        messages.error(request, 'No file uploaded.')
        return redirect('settings:counties')
    
    file = request.FILES['file']
    
    try:
        decoded = file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
        
        imported = 0
        updated = 0
        errors = 0
        error_messages = []
        
        region_map = {
            'coast': 'coast',
            'eastern': 'eastern',
            'north eastern': 'north_eastern',
            'north_eastern': 'north_eastern',
            'central': 'central',
            'rift valley': 'rift_valley',
            'rift_valley': 'rift_valley',
            'western': 'western',
            'nairobi': 'nairobi',
        }
        
        for row in reader:
            try:
                code = row.get('Code', '').strip()
                name = row.get('Name', '').strip()
                headquarters = row.get('Headquarters', '').strip()
                region = row.get('Region', '').strip().lower()
                population = row.get('Population', '').strip()
                area = row.get('Area (sq km)', '').strip()
                active = row.get('Active', 'Yes').strip().lower() in ['yes', 'true', '1', 'active']
                
                if not code or not name:
                    errors += 1
                    error_messages.append(f"Missing code or name: {row}")
                    continue
                
                region_code = region_map.get(region, '')
                
                if County.objects.filter(code=code).exists():
                    county = County.objects.get(code=code)
                    county.name = name
                    county.headquarters = headquarters
                    county.region = region_code
                    county.population = population if population else None
                    county.area_sq_km = area if area else None
                    county.is_active = active
                    county.save()
                    updated += 1
                else:
                    County.objects.create(
                        code=code,
                        name=name,
                        headquarters=headquarters,
                        region=region_code,
                        population=population if population else None,
                        area_sq_km=area if area else None,
                        is_active=active
                    )
                    imported += 1
            except Exception as e:
                errors += 1
                error_messages.append(str(e))
        
        messages.success(request, f'Imported {imported} new counties, Updated {updated} counties. Errors: {errors}')
        if error_messages:
            for msg in error_messages[:3]:
                messages.warning(request, msg)
        
    except Exception as e:
        messages.error(request, f'Error processing file: {str(e)}')
    
    return redirect('settings:counties')