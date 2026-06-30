from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from .models import Indicator, ThematicArea
from users.decorators import module_permission_required, permission_required


@login_required
@module_permission_required('indicators', 'view')
def indicator_list(request):
    """List all indicators - Uses database permissions"""
    thematic_areas = ThematicArea.objects.all()
    indicators = Indicator.objects.filter(is_active=True)
    
    # Apply filters
    area_filter = request.GET.get('thematic_area')
    type_filter = request.GET.get('indicator_type')
    freq_filter = request.GET.get('frequency')
    search_query = request.GET.get('search')
    
    if area_filter:
        indicators = indicators.filter(thematic_area_id=area_filter)
    if type_filter:
        indicators = indicators.filter(indicator_type=type_filter)
    if freq_filter:
        indicators = indicators.filter(frequency=freq_filter)
    if search_query:
        indicators = indicators.filter(
            Q(code__icontains=search_query) | 
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    context = {
        'indicators': indicators,
        'areas': thematic_areas,
        'can_add': request.user.has_module_permission('indicators', 'add'),
        'can_edit': request.user.has_module_permission('indicators', 'change'),
        'can_delete': request.user.has_module_permission('indicators', 'delete'),
        'total_count': indicators.count(),
    }
    return render(request, 'indicators/list.html', context)

@login_required
@module_permission_required('indicators', 'view')
def indicator_detail(request, code):
    """Get indicator details for AJAX view - Uses database permissions"""
    try:
        indicator = get_object_or_404(Indicator, code=code)
        
        data = {
            'code': indicator.code,
            'name': indicator.name,
            'thematic_area': indicator.thematic_area.name,
            'indicator_type': indicator.get_indicator_type_display(),
            'data_type': indicator.get_data_type_display(),
            'unit': indicator.unit or '',
            'target_value': str(indicator.target_value) if indicator.target_value else None,
            'min_value': str(indicator.min_value) if indicator.min_value else None,
            'max_value': str(indicator.max_value) if indicator.max_value else None,
            'frequency': indicator.get_frequency_display(),
            'source_system': indicator.source_system or '',
            'description': indicator.description or '',
            'created_at': indicator.created_at.strftime('%B %d, %Y %H:%M') if indicator.created_at else None,
            'is_active': indicator.is_active,
            'range_display': indicator.get_range_display(),
        }
        
        return JsonResponse(data)
        
    except Indicator.DoesNotExist:
        return JsonResponse({
            'error': 'Indicator not found',
            'message': f'Indicator with code "{code}" does not exist'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'error': 'Server error',
            'message': str(e)
        }, status=500)

@login_required
@module_permission_required('indicators', 'view')
def indicator_detail_api(request, code):
    """API endpoint for indicator details - Used by AJAX modal"""
    try:
        indicator = get_object_or_404(Indicator, code=code)
        
        data = {
            'code': indicator.code,
            'name': indicator.name,
            'thematic_area': indicator.thematic_area.name,
            'indicator_type': indicator.get_indicator_type_display(),
            'data_type': indicator.get_data_type_display(),
            'unit': indicator.unit or '',
            'target_value': str(indicator.target_value) if indicator.target_value else None,
            'min_value': str(indicator.min_value) if indicator.min_value else None,
            'max_value': str(indicator.max_value) if indicator.max_value else None,
            'frequency': indicator.get_frequency_display(),
            'source_system': indicator.source_system or '',
            'description': indicator.description or '',
            'created_at': indicator.created_at.strftime('%B %d, %Y %H:%M') if indicator.created_at else None,
            'is_active': indicator.is_active,
            'range_display': indicator.get_range_display(),
        }
        
        return JsonResponse(data)
        
    except Indicator.DoesNotExist:
        return JsonResponse({
            'error': 'Indicator not found',
            'message': f'Indicator with code "{code}" does not exist'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'error': 'Server error',
            'message': str(e)
        }, status=500)

@login_required
@module_permission_required('indicators', 'add')
def indicator_add(request):
    """Add a new indicator - Uses database permissions"""
    if request.method == 'POST':
        try:
            code = request.POST.get('code', '').strip()
            name = request.POST.get('name', '').strip()
            thematic_area_id = request.POST.get('thematic_area')
            indicator_type = request.POST.get('indicator_type')
            data_type = request.POST.get('data_type')
            unit = request.POST.get('unit', '').strip()
            target_value = request.POST.get('target_value')
            source_system = request.POST.get('source_system', '').strip()
            frequency = request.POST.get('frequency')
            description = request.POST.get('description', '').strip()
            min_value = request.POST.get('min_value')
            max_value = request.POST.get('max_value')
            
            # Validation
            if not code or not name:
                messages.error(request, 'Code and Name are required.')
                areas = ThematicArea.objects.all()
                return render(request, 'indicators/form.html', {'areas': areas})
            
            if Indicator.objects.filter(code=code).exists():
                messages.error(request, f'Indicator with code "{code}" already exists.')
                areas = ThematicArea.objects.all()
                return render(request, 'indicators/form.html', {'areas': areas})
            
            thematic_area = ThematicArea.objects.get(id=thematic_area_id)
            
            Indicator.objects.create(
                code=code,
                name=name,
                thematic_area=thematic_area,
                indicator_type=indicator_type,
                data_type=data_type,
                unit=unit,
                target_value=float(target_value) if target_value else None,
                source_system=source_system,
                frequency=frequency,
                description=description,
                min_value=float(min_value) if min_value else None,
                max_value=float(max_value) if max_value else None,
                created_by=request.user
            )
            messages.success(request, f'Indicator "{code}" added successfully!')
            return redirect('indicators:list')
            
        except ThematicArea.DoesNotExist:
            messages.error(request, 'Invalid thematic area selected.')
        except ValueError as e:
            messages.error(request, f'Invalid numeric value: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error adding indicator: {str(e)}')
    
    areas = ThematicArea.objects.all()
    return render(request, 'indicators/form.html', {'areas': areas, 'is_edit': False})

@login_required
@module_permission_required('indicators', 'change')
def indicator_edit(request, code):
    """Edit an indicator - Uses database permissions"""
    indicator = get_object_or_404(Indicator, code=code)
    
    if request.method == 'POST':
        try:
            indicator.name = request.POST.get('name', '').strip()
            indicator.thematic_area_id = request.POST.get('thematic_area')
            indicator.indicator_type = request.POST.get('indicator_type')
            indicator.data_type = request.POST.get('data_type')
            indicator.unit = request.POST.get('unit', '').strip()
            target_value = request.POST.get('target_value')
            indicator.target_value = float(target_value) if target_value else None
            indicator.source_system = request.POST.get('source_system', '').strip()
            indicator.frequency = request.POST.get('frequency')
            indicator.description = request.POST.get('description', '').strip()
            min_value = request.POST.get('min_value')
            indicator.min_value = float(min_value) if min_value else None
            max_value = request.POST.get('max_value')
            indicator.max_value = float(max_value) if max_value else None
            
            indicator.save()
            messages.success(request, f'Indicator "{code}" updated successfully!')
            return redirect('indicators:list')
            
        except ValueError as e:
            messages.error(request, f'Invalid numeric value: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error updating indicator: {str(e)}')
    
    areas = ThematicArea.objects.all()
    return render(request, 'indicators/form.html', {
        'indicator': indicator, 
        'areas': areas,
        'is_edit': True
    })


@login_required
@module_permission_required('indicators', 'delete')
def indicator_delete(request, code):
    """Delete (deactivate) an indicator - Uses database permissions"""
    indicator = get_object_or_404(Indicator, code=code)
    
    if request.method == 'POST':
        indicator.is_active = False
        indicator.save()
        messages.success(request, f'Indicator "{code}" deactivated successfully!')
        return redirect('indicators:list')
    
    return render(request, 'indicators/delete.html', {'indicator': indicator})


@login_required
@permission_required('can_manage_thematic_areas')
def thematic_area_list(request):
    """List thematic areas - Uses database permissions"""
    areas = ThematicArea.objects.all()
    return render(request, 'indicators/thematic_areas.html', {'areas': areas})


@login_required
@permission_required('can_manage_thematic_areas')
def thematic_area_add(request):
    """Add a new thematic area - Uses database permissions"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip().upper()
        description = request.POST.get('description', '').strip()
        
        if not name or not code:
            messages.error(request, 'Name and Code are required.')
            return render(request, 'indicators/thematic_area_form.html')
        
        if ThematicArea.objects.filter(code=code).exists():
            messages.error(request, f'Thematic area with code "{code}" already exists.')
            return render(request, 'indicators/thematic_area_form.html')
        
        if ThematicArea.objects.filter(name=name).exists():
            messages.error(request, f'Thematic area with name "{name}" already exists.')
            return render(request, 'indicators/thematic_area_form.html')
        
        ThematicArea.objects.create(
            name=name,
            code=code,
            description=description
        )
        messages.success(request, f'Thematic area "{name}" added successfully!')
        return redirect('indicators:thematic_areas')
    
    return render(request, 'indicators/thematic_area_form.html')


@login_required
@permission_required('can_manage_thematic_areas')
def thematic_area_edit(request, pk):
    """Edit a thematic area - Uses database permissions"""
    area = get_object_or_404(ThematicArea, pk=pk)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip().upper()
        description = request.POST.get('description', '').strip()
        
        if not name or not code:
            messages.error(request, 'Name and Code are required.')
            return render(request, 'indicators/thematic_area_form.html', {'area': area})
        
        # Check for duplicates (excluding current)
        if ThematicArea.objects.filter(code=code).exclude(pk=pk).exists():
            messages.error(request, f'Thematic area with code "{code}" already exists.')
            return render(request, 'indicators/thematic_area_form.html', {'area': area})
        
        if ThematicArea.objects.filter(name=name).exclude(pk=pk).exists():
            messages.error(request, f'Thematic area with name "{name}" already exists.')
            return render(request, 'indicators/thematic_area_form.html', {'area': area})
        
        area.name = name
        area.code = code
        area.description = description
        area.save()
        
        messages.success(request, f'Thematic area "{name}" updated successfully!')
        return redirect('indicators:thematic_areas')
    
    return render(request, 'indicators/thematic_area_form.html', {'area': area})


@login_required
@permission_required('can_manage_thematic_areas')
def thematic_area_delete(request, pk):
    """Delete a thematic area - Uses database permissions"""
    area = get_object_or_404(ThematicArea, pk=pk)
    
    # Check if area has indicators
    if area.indicators.filter(is_active=True).exists():
        messages.error(request, f'Cannot delete "{area.name}" - it has active indicators.')
        return redirect('indicators:thematic_areas')
    
    if request.method == 'POST':
        area.delete()
        messages.success(request, f'Thematic area "{area.name}" deleted successfully!')
        return redirect('indicators:thematic_areas')
    
    return render(request, 'indicators/thematic_area_delete.html', {'area': area})