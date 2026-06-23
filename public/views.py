from django.shortcuts import render
from django.http import JsonResponse
from indicators.models import Indicator, ThematicArea
from core.models import County
from data_entry.models import DataEntry

def landing(request):
    return render(request, 'public/landing.html')

def stats_api(request):
    data = {
        'indicators': Indicator.objects.filter(is_active=True).count(),
        'counties': County.objects.filter(is_active=True).count(),
        'thematic_areas': ThematicArea.objects.count(),
        'submissions': DataEntry.objects.filter(status='approved').count(),
    }
    return JsonResponse(data)
