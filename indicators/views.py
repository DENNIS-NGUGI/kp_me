from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Indicator, ThematicArea

def user_can_manage_indicators(user):
    return user.is_superuser or (user.role and user.role.name in ['admin', 'ncpd_me'])

@login_required
def indicator_list(request):
    thematic_areas = ThematicArea.objects.all()
    indicators = Indicator.objects.filter(is_active=True)
    
    # Apply filters
    area_filter = request.GET.get('thematic_area')
    type_filter = request.GET.get('indicator_type')
    freq_filter = request.GET.get('frequency')
    
    if area_filter:
        indicators = indicators.filter(thematic_area_id=area_filter)
    if type_filter:
        indicators = indicators.filter(indicator_type=type_filter)
    if freq_filter:
        indicators = indicators.filter(frequency=freq_filter)
    
    context = {
        'indicators': indicators,
        'areas': thematic_areas,
    }
    return render(request, 'indicators/list.html', context)

@login_required
@user_passes_test(user_can_manage_indicators)
def indicator_add(request):
    if request.method == 'POST':
        try:
            code = request.POST.get('code')
            name = request.POST.get('name')
            thematic_area_id = request.POST.get('thematic_area')
            indicator_type = request.POST.get('indicator_type')
            data_type = request.POST.get('data_type')
            unit = request.POST.get('unit')
            target_value = request.POST.get('target_value')
            source_system = request.POST.get('source_system')
            frequency = request.POST.get('frequency')
            description = request.POST.get('description')
            min_value = request.POST.get('min_value')
            max_value = request.POST.get('max_value')
            
            thematic_area = ThematicArea.objects.get(id=thematic_area_id)
            
            Indicator.objects.create(
                code=code,
                name=name,
                thematic_area=thematic_area,
                indicator_type=indicator_type,
                data_type=data_type,
                unit=unit,
                target_value=target_value if target_value else None,
                source_system=source_system,
                frequency=frequency,
                description=description,
                min_value=min_value if min_value else None,
                max_value=max_value if max_value else None,
                created_by=request.user
            )
            messages.success(request, f'Indicator {code} added successfully!')
            return redirect('indicators:list')
        except Exception as e:
            messages.error(request, f'Error adding indicator: {str(e)}')
    
    areas = ThematicArea.objects.all()
    return render(request, 'indicators/form.html', {'areas': areas})

@login_required
@user_passes_test(user_can_manage_indicators)
def indicator_edit(request, code):
    indicator = get_object_or_404(Indicator, code=code)
    
    if request.method == 'POST':
        try:
            indicator.name = request.POST.get('name')
            indicator.thematic_area_id = request.POST.get('thematic_area')
            indicator.indicator_type = request.POST.get('indicator_type')
            indicator.data_type = request.POST.get('data_type')
            indicator.unit = request.POST.get('unit')
            indicator.target_value = request.POST.get('target_value') or None
            indicator.source_system = request.POST.get('source_system')
            indicator.frequency = request.POST.get('frequency')
            indicator.description = request.POST.get('description')
            indicator.min_value = request.POST.get('min_value') or None
            indicator.max_value = request.POST.get('max_value') or None
            indicator.save()
            messages.success(request, f'Indicator {code} updated successfully!')
            return redirect('indicators:list')
        except Exception as e:
            messages.error(request, f'Error updating indicator: {str(e)}')
    
    areas = ThematicArea.objects.all()
    return render(request, 'indicators/form.html', {'indicator': indicator, 'areas': areas})

@login_required
@user_passes_test(user_can_manage_indicators)
def indicator_delete(request, code):
    indicator = get_object_or_404(Indicator, code=code)
    indicator.is_active = False
    indicator.save()
    messages.success(request, f'Indicator {code} deactivated successfully!')
    return redirect('indicators:list')

@login_required
def thematic_area_list(request):
    areas = ThematicArea.objects.all()
    return render(request, 'indicators/thematic_areas.html', {'areas': areas})
