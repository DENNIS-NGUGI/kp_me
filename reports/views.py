import io
import json
import csv
import logging
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.db.models import Count, Q, Avg, Sum
from django.utils import timezone
from datetime import datetime, timedelta
from io import BytesIO
from django.contrib import messages
from django.views.decorators.cache import cache_page
from django.views.decorators.cache import cache_control
from django.conf import settings
from data_entry.models import DataEntry
from indicators.models import Indicator, ThematicArea
from core.models import County, Quarter
from users.decorators import (
    permission_required, 
    module_permission_required,
    view_reports_required, 
    admin_required, 
    ncpd_or_admin_required
)

# Import optimized aggregation functions
from .aggregations import (
    count_entries_met,
    get_thematic_performance,
    get_quarterly_performance,
    get_county_performance,
    get_county_map_data,
    audit_log_export,
    rate_limit_check
)
from .models import ReportAccessPolicy
from users.models import Role, User

# Setup logger for exports
logger = logging.getLogger('data_export')


@login_required
@cache_control(private=True, max_age=86400)
def county_map_boundaries(request):
    """Return the local Kenya county boundaries used by the dashboard map."""
    boundary_file = Path(settings.BASE_DIR) / 'static' / 'map' / 'kenyan-counties.geojson'
    with boundary_file.open(encoding='utf-8') as geojson_file:
        return JsonResponse(json.load(geojson_file), safe=False)

# ============================================
# DASHBOARD - Uses database permissions
# ============================================
@login_required
def dashboard(request):
    # Check if user has either view_reports or view_dashboard permission
    if not (request.user.has_permission('view_reports') or 
            request.user.has_module_permission('dashboard', 'view')):
        messages.error(request, "You don't have permission to view the dashboard.")
        return redirect('users:permission_denied')

    user = request.user
    
    # ===== RBAC: DETERMINE USER'S DATA SCOPE USING DATABASE PERMISSIONS =====
    
    # Use the property from the model
    is_county_user = user.is_county_user
    
    # Check if user can view all data (admin/ncpd/policy_maker)
    can_view_all = user.is_superuser or user.has_any_permission(
        'can_approve_data', 
        'can_manage_indicators',
        'view_county_data'
    )
    
    if is_county_user:
        # County users only see their assigned counties.
        counties = user.counties.all()
        entries = DataEntry.objects.filter(county__in=counties, status='approved')
        all_entries = DataEntry.objects.filter(county__in=counties)
        user_scope = f"Counties: {', '.join(counties.values_list('name', flat=True))}"
        county_name = None
        county = None
    elif can_view_all:
        # Admin/NCPD/Policy Maker see all data
        entries = DataEntry.objects.filter(status='approved')
        all_entries = DataEntry.objects.all()
        counties = County.objects.filter(is_active=True)
        user_scope = "All Counties"
        county_name = None
        county = None
    else:
        # Fallback - limited access
        entries = DataEntry.objects.none()
        all_entries = DataEntry.objects.none()
        counties = County.objects.none()
        user_scope = "Limited Access"
        county_name = None
        county = None
    
    # ===== STATISTICS =====
    total_indicators = Indicator.objects.filter(is_active=True).count()
    
    if is_county_user and county:
        county_indicator_ids = entries.values_list('indicator_id', flat=True).distinct()
        total_indicators_with_data = Indicator.objects.filter(
            is_active=True, 
            id__in=county_indicator_ids
        ).count()
        total_indicators = total_indicators_with_data if total_indicators_with_data > 0 else Indicator.objects.filter(is_active=True).count()
    
    total_counties = counties.count()
    total_entries = all_entries.exclude(status='draft').count()
    approved_entries = entries.filter(status='approved').count()
    
    # Pending approvals - only for users with approval permission
    if user.has_permission('can_approve_data'):
        if is_county_user and county:
            pending_approvals = DataEntry.objects.filter(county=county, status='submitted').count()
        else:
            pending_approvals = DataEntry.objects.filter(status='submitted').count()
    else:
        pending_approvals = 0
    
    # ===== SUBMISSION RATE =====
    today = timezone.localdate()
    current_quarter = Quarter.objects.filter(
        is_active=True,
        is_closed=False,
        start_date__lte=today,
        end_date__gte=today,
    ).first()
    current_quarter_label = (
        f"Q{current_quarter.quarter_number} {current_quarter.start_date.year}"
        if current_quarter else None
    )
    submission_rate = 0
    if current_quarter:
        if is_county_user and county:
            has_submitted = DataEntry.objects.filter(
                county=county,
                quarter=current_quarter,
                status__in=['submitted', 'approved']
            ).exists()
            submission_rate = 100 if has_submitted else 0
        elif can_view_all:
            total_counties_for_quarter = County.objects.filter(is_active=True).count()
            submitted_counties = DataEntry.objects.filter(
                quarter=current_quarter,
                status__in=['submitted', 'approved']
            ).values('county').distinct().count()
            submission_rate = round((submitted_counties / total_counties_for_quarter * 100) if total_counties_for_quarter > 0 else 0)
    
    # ===== OVERALL PERFORMANCE - OPTIMIZED AGGREGATION =====
    if total_entries > 0:
        try:
            counts = count_entries_met(entries)
            overall_performance = round((counts['met'] / total_entries * 100))
        except Exception as e:
            logger.error(f"Error calculating performance: {str(e)}")
            overall_performance = 0
    else:
        overall_performance = 0
    
    # ===== COUNTIES WITH NO DATA =====
    if is_county_user and county:
        has_data = entries.exists()
        counties_with_no_data = 0 if has_data else 1
    elif can_view_all:
        all_counties = County.objects.filter(is_active=True)
        counties_with_data = DataEntry.objects.filter(
            status='approved'
        ).values('county').distinct()
        counties_with_data_ids = [c['county'] for c in counties_with_data]
        counties_with_no_data = all_counties.exclude(id__in=counties_with_data_ids).count()
    else:
        counties_with_no_data = 0
    
    # ===== THEMATIC PERFORMANCE - OPTIMIZED AGGREGATION =====
    try:
        thematic_performance = get_thematic_performance(entries)
        # Filter empty results for county users
        if is_county_user:
            thematic_performance = [p for p in thematic_performance if p['total_entries'] > 0]
    except Exception as e:
        logger.error(f"Error calculating thematic performance: {str(e)}")
        thematic_performance = []
    
    # ===== QUARTERLY PERFORMANCE DATA FOR CHART - OPTIMIZED AGGREGATION =====
    try:
        chart_quarters_data = get_quarterly_performance(entries)
        
        chart_labels = [q['name'] for q in chart_quarters_data]
        chart_data = [q['percentage'] for q in chart_quarters_data]
        chart_target = [65] * len(chart_labels)
        
        if not chart_labels:
            chart_labels = ['No Data']
            chart_data = [0]
            chart_target = [65]
    except Exception as e:
        logger.error(f"Error calculating quarterly performance: {str(e)}")
        chart_labels = ['No Data']
        chart_data = [0]
        chart_target = [65]
        chart_quarters_data = []
    
    # ===== STATUS DISTRIBUTION =====
    if is_county_user and county:
        status_data = {
            'approved': DataEntry.objects.filter(county=county, status='approved').count(),
            'submitted': DataEntry.objects.filter(county=county, status='submitted').count(),
            'rejected': DataEntry.objects.filter(county=county, status='rejected').count(),
            'draft': DataEntry.objects.filter(county=county, status='draft').count(),
        }
    elif can_view_all:
        status_data = {
            'approved': DataEntry.objects.filter(status='approved').count(),
            'submitted': DataEntry.objects.filter(status='submitted').count(),
            'rejected': DataEntry.objects.filter(status='rejected').count(),
            'draft': DataEntry.objects.filter(status='draft').count(),
        }
    else:
        status_data = {
            'approved': 0,
            'submitted': 0,
            'rejected': 0,
            'draft': 0,
        }
    
    # ===== COUNTY PERFORMANCE - OPTIMIZED AGGREGATION =====
    try:
        county_performance = get_county_performance(entries, counties)
        county_map_data = get_county_map_data(entries, all_entries, counties)
    except Exception as e:
        logger.error(f"Error calculating county performance: {str(e)}")
        county_performance = []
        county_map_data = []
    
    # ===== RECENT ACTIVITY =====
    recent_entries = entries.select_related('county', 'quarter', 'indicator', 'indicator__thematic_area').order_by('-created_at')[:10]
    
    # ===== ADDITIONAL ANALYTICS =====
    # Most active counties (with most submissions)
    if can_view_all:
        most_active_counties = DataEntry.objects.filter(status='approved').values('county__name').annotate(
            total=Count('id')
        ).order_by('-total')[:5]
    else:
        most_active_counties = []
    
    # ===== INDICATOR COMPLETION RATE - OPTIMIZED =====
    indicator_completion = {}
    try:
        for ind in Indicator.objects.filter(is_active=True)[:10]:
            ind_entries = entries.filter(indicator=ind)
            if ind_entries.count() > 0:
                counts = count_entries_met(ind_entries)
                indicator_completion[ind.code] = {
                    'name': ind.name,
                    'total': counts['total'],
                    'met': counts['met'],
                    'percentage': round((counts['met'] / counts['total'] * 100) if counts['total'] > 0 else 0)
                }
    except Exception as e:
        logger.error(f"Error calculating indicator completion: {str(e)}")
    
    context = {
        # Stats
        'total_indicators': total_indicators,
        'total_counties': total_counties,
        'total_entries': total_entries,
        'approved_entries': approved_entries,
        'pending_approvals': pending_approvals,
        'submission_rate': submission_rate,
        'current_quarter': current_quarter,
        'current_quarter_label': current_quarter_label,
        'overall_performance': overall_performance,
        'counties_with_no_data': counties_with_no_data,
        'user_scope': user_scope,
        
        # Thematic performance
        'thematic_performance': thematic_performance,
        
        # Chart data (as JSON)
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'chart_target': json.dumps(chart_target),
        'chart_quarters_data': chart_quarters_data,
        
        # Status data
        'status_data': status_data,
        
        # County performance
        'county_performance': county_performance,
        'county_map_data': json.dumps(county_map_data),
        'data_entry_list_url': reverse('data_entry:list'),
        'can_view_data_entry': user.has_module_permission('data_entry', 'view'),
        
        # Recent entries
        'recent_entries': recent_entries,
        
        # Additional analytics
        'most_active_counties': most_active_counties,
        'indicator_completion': indicator_completion,
        
        # User info
        'user_role': user.role.get_display_name() if user.role else 'No Role',
        'is_superuser': user.is_superuser,
        'is_county_user': is_county_user,
        'county_name': county_name,
    }
    
    return render(request, 'reports/dashboard.html', context)

# ============================================
# REPORT LIST - Uses database permissions
# ============================================

@login_required
@view_reports_required
def report_list(request):
    """List all available reports - FULLY DATABASE DRIVEN"""
    user = request.user
    
    # Base querysets
    thematic_areas = ThematicArea.objects.all()
    indicators = Indicator.objects.filter(is_active=True)
    quarters = Quarter.objects.filter(is_active=True)
    
    # ===== RBAC: DETERMINE USER'S DATA SCOPE USING DATABASE PERMISSIONS =====
    is_county_user = user.has_permission('manage_county_data') and user.is_county_user
    can_view_all = user.is_superuser or user.has_any_permission(
        'can_approve_data', 
        'can_manage_indicators',
        'view_county_data'
    )
    
    if is_county_user:
        # County users only see their assigned counties.
        counties = user.counties.all()
        county_entries = DataEntry.objects.filter(county__in=counties, status='approved')
        # Get indicators that have data for this county
        indicators = indicators.filter(
            id__in=county_entries.values_list('indicator_id', flat=True).distinct()
        )
        # Get thematic areas that have indicators with data
        thematic_areas = thematic_areas.filter(
            id__in=indicators.values_list('thematic_area_id', flat=True).distinct()
        )
        # Get quarters that have data for this county
        quarters = quarters.filter(
            id__in=county_entries.values_list('quarter_id', flat=True).distinct()
        )
    elif can_view_all:
        # Admin/NCPD/Policy Maker see all counties
        counties = County.objects.filter(is_active=True)
    else:
        counties = County.objects.none()
    
    # Get pending approvals count - only for users with approval permission
    pending_count = 0
    if user.has_permission('can_approve_data'):
        pending_count = DataEntry.objects.filter(status='submitted').count()

    report_modules = {}
    for report_key, report in REPORT_CATALOGUE.items():
        if _user_can_access_report(request.user, report_key):
            report_modules.setdefault(report['module'], []).append((report_key, report))
    
    context = {
        'thematic_areas': thematic_areas,
        'counties': counties,
        'quarters': quarters,
        'indicators': indicators,
        'pending_count': pending_count,
        'user_role': user.role.get_display_name() if user.role else 'No Role',
        'is_county_user': is_county_user,
        'county_name': ', '.join(user.counties.values_list('name', flat=True)) if user.is_county_user else None,
        'report_modules': report_modules,
    }
    return render(request, 'reports/catalogue.html', context)


# ============================================
# GENERATE REPORT - Uses database permissions
# ============================================

@login_required
@view_reports_required
def generate_report(request):
    """Generate custom report based on filters - FULLY DATABASE DRIVEN"""
    user = request.user
    is_county_user = user.has_permission('manage_county_data') and user.is_county_user
    
    if request.method == 'POST':
        report_type = request.POST.get('report_type')
        county_id = request.POST.get('county')
        quarter_id = request.POST.get('quarter')
        thematic_area_id = request.POST.get('thematic_area')
        indicator_id = request.POST.get('indicator')
        format_type = request.POST.get('format', 'html')
        
        # Build query - ONLY APPROVED
        query = Q(status='approved')
        if county_id:
            query &= Q(county_id=county_id)
        if quarter_id:
            query &= Q(quarter_id=quarter_id)
        if thematic_area_id:
            indicators = Indicator.objects.filter(thematic_area_id=thematic_area_id)
            query &= Q(indicator__in=indicators)
        if indicator_id:
            query &= Q(indicator_id=indicator_id)
        
        # RBAC: County users only see their county
        if is_county_user:
            query &= Q(county__in=user.counties.all())
        
        entries = DataEntry.objects.filter(query).order_by('-created_at')
        
        if format_type == 'csv':
            return export_csv(entries)
        elif format_type == 'json':
            return export_json(entries)
        else:
            return render(request, 'reports/result.html', {'entries': entries})
    
    # GET - show form
    counties = County.objects.filter(is_active=True)
    quarters = Quarter.objects.filter(is_active=True)
    thematic_areas = ThematicArea.objects.all()
    indicators = Indicator.objects.filter(is_active=True)
    
    # RBAC: County users only see their county
    if is_county_user:
        counties = user.counties.all()
    
    context = {
        'counties': counties,
        'quarters': quarters,
        'thematic_areas': thematic_areas,
        'indicators': indicators,
    }
    return render(request, 'reports/generate.html', context)


# ============================================
# QUARTERLY REPORT - Uses database permissions
# ============================================

@login_required
@view_reports_required
def quarterly_report(request):
    """Generate quarterly report - FULLY DATABASE DRIVEN"""
    user = request.user
    is_county_user = user.has_permission('manage_county_data') and user.is_county_user
    can_view_all = user.is_superuser or user.has_any_permission(
        'can_approve_data', 
        'can_manage_indicators',
        'view_county_data'
    )
    
    quarter_id = request.GET.get('quarter')
    county_id = request.GET.get('county')
    
    quarter = get_object_or_404(Quarter, id=quarter_id) if quarter_id else Quarter.objects.filter(is_active=True).first()
    
    if not quarter:
        return render(request, 'reports/quarterly.html', {'error': 'No active quarter found'})
    
    # Build query - APPROVED ONLY
    query = Q(quarter=quarter, status='approved')
    
    # ===== RBAC USING DATABASE PERMISSIONS =====
    if county_id:
        # Check if user has permission to view this county's data
        if is_county_user and not user.counties.filter(id=county_id).exists():
            messages.error(request, 'You do not have permission to view data for this county.')
            return redirect('reports:quarterly_report')
        query &= Q(county_id=county_id)
        county = get_object_or_404(County, id=county_id)
    elif is_county_user:
        query &= Q(county__in=user.counties.all())
        county = None
    elif can_view_all:
        county = None
    else:
        messages.error(request, 'You do not have permission to view reports.')
        return redirect('reports:report_list')
    
    entries = DataEntry.objects.filter(query).select_related('county', 'indicator', 'indicator__thematic_area')
    
    # Group by thematic area
    thematic_data = {}
    for entry in entries:
        area_name = entry.indicator.thematic_area.name
        if area_name not in thematic_data:
            thematic_data[area_name] = {
                'total': 0,
                'met': 0,
                'not_met': 0,
                'no_data': 0,
                'entries': []
            }
        thematic_data[area_name]['total'] += 1
        if entry.is_met() is True:
            thematic_data[area_name]['met'] += 1
        elif entry.is_met() is False:
            thematic_data[area_name]['not_met'] += 1
        else:
            thematic_data[area_name]['no_data'] += 1
        thematic_data[area_name]['entries'].append(entry)
    
    # County performance
    county_performance = {}
    for entry in entries:
        county_name = entry.county.name
        if county_name not in county_performance:
            county_performance[county_name] = {
                'total': 0,
                'met': 0,
                'not_met': 0,
                'entries': []
            }
        county_performance[county_name]['total'] += 1
        if entry.is_met() is True:
            county_performance[county_name]['met'] += 1
        elif entry.is_met() is False:
            county_performance[county_name]['not_met'] += 1
        county_performance[county_name]['entries'].append(entry)
    
    # Calculate overall
    total_entries = entries.count()
    total_met = sum(1 for e in entries if e.is_met() is True)
    total_not_met = sum(1 for e in entries if e.is_met() is False)
    total_no_data = sum(1 for e in entries if e.is_met() is None)
    
    context = {
        'quarter': quarter,
        'county': county,
        'thematic_data': thematic_data,
        'county_performance': county_performance,
        'total_entries': total_entries,
        'total_met': total_met,
        'total_not_met': total_not_met,
        'total_no_data': total_no_data,
        'user_role': user.role.get_display_name() if user.role else 'No Role',
    }
    return render(request, 'reports/quarterly.html', context)


# ============================================
# ANNUAL REPORT - Uses database permissions
# ============================================

@login_required
@view_reports_required
def annual_report(request):
    """Generate annual report - FULLY DATABASE DRIVEN"""
    user = request.user
    is_county_user = user.has_permission('manage_county_data') and user.is_county_user
    can_view_all = user.is_superuser or user.has_any_permission(
        'can_approve_data', 
        'can_manage_indicators',
        'view_county_data'
    )
    
    year = request.GET.get('year', timezone.now().year)
    county_id = request.GET.get('county')
    
    quarters = Quarter.objects.filter(
        start_date__year=year
    ).order_by('start_date')
    
    if not quarters:
        return render(request, 'reports/annual.html', {
            'error': f'No quarters found for year {year}',
            'year': year
        })
    
    # Build query - APPROVED ONLY
    query = Q(quarter__in=quarters, status='approved')
    
    # ===== RBAC USING DATABASE PERMISSIONS =====
    if county_id:
        if is_county_user and not user.counties.filter(id=county_id).exists():
            messages.error(request, 'You do not have permission to view data for this county.')
            return redirect('reports:annual_report')
        query &= Q(county_id=county_id)
        county = get_object_or_404(County, id=county_id)
    elif is_county_user:
        query &= Q(county__in=user.counties.all())
        county = None
    elif can_view_all:
        county = None
    else:
        messages.error(request, 'You do not have permission to view annual reports.')
        return redirect('reports:report_list')
    
    entries = DataEntry.objects.filter(query).select_related('county', 'indicator', 'quarter')
    
    # Quarter-by-quarter performance
    quarterly_performance = {}
    for q in quarters:
        q_entries = entries.filter(quarter=q)
        quarterly_performance[q.name] = {
            'total': q_entries.count(),
            'met': sum(1 for e in q_entries if e.is_met() is True),
            'not_met': sum(1 for e in q_entries if e.is_met() is False),
            'no_data': sum(1 for e in q_entries if e.is_met() is None),
        }
    
    # Thematic performance for the year
    thematic_performance = {}
    for area in ThematicArea.objects.all():
        area_entries = entries.filter(indicator__thematic_area=area)
        met_count = sum(1 for e in area_entries if e.is_met() is True)
        thematic_performance[area.name] = {
            'total': area_entries.count(),
            'met': met_count,
            'not_met': sum(1 for e in area_entries if e.is_met() is False),
            'no_data': sum(1 for e in area_entries if e.is_met() is None),
            'percentage': round((met_count / area_entries.count() * 100) if area_entries.count() > 0 else 0)
        }
    
    total_entries = entries.count()
    total_met = sum(1 for e in entries if e.is_met() is True)
    total_not_met = sum(1 for e in entries if e.is_met() is False)
    total_no_data = sum(1 for e in entries if e.is_met() is None)
    
    context = {
        'year': year,
        'county': county,
        'quarters': quarters,
        'quarterly_performance': quarterly_performance,
        'thematic_performance': thematic_performance,
        'total_entries': total_entries,
        'total_met': total_met,
        'total_not_met': total_not_met,
        'total_no_data': total_no_data,
        'overall_percentage': round((total_met / total_entries * 100) if total_entries > 0 else 0),
        'user_role': user.role.get_display_name() if user.role else 'No Role',
    }
    return render(request, 'reports/annual.html', context)


# ============================================
# THEMATIC REPORT - Uses database permissions
# ============================================

@login_required
@view_reports_required
def thematic_report(request, code):
    """Generate report for a specific thematic area - FULLY DATABASE DRIVEN"""
    user = request.user
    is_county_user = user.has_permission('manage_county_data') and user.is_county_user
    
    area = get_object_or_404(ThematicArea, code=code)
    indicators = Indicator.objects.filter(thematic_area=area, is_active=True)
    
    quarter_id = request.GET.get('quarter')
    county_id = request.GET.get('county')
    
    # Build query - APPROVED ONLY
    query = Q(indicator__in=indicators, status='approved')
    if quarter_id:
        query &= Q(quarter_id=quarter_id)
    if county_id:
        if is_county_user and not user.counties.filter(id=county_id).exists():
            messages.error(request, 'You do not have permission to view data for this county.')
            return redirect('reports:thematic_report', code=code)
        query &= Q(county_id=county_id)
    elif is_county_user:
        query &= Q(county__in=user.counties.all())
    
    entries = DataEntry.objects.filter(query).select_related('county', 'quarter', 'indicator')
    
    # Group by indicator
    indicator_performance = {}
    for ind in indicators:
        ind_entries = entries.filter(indicator=ind)
        met_count = sum(1 for e in ind_entries if e.is_met() is True)
        indicator_performance[ind.code] = {
            'name': ind.name,
            'target': ind.target_value,
            'unit': ind.unit,
            'total': ind_entries.count(),
            'met': met_count,
            'not_met': sum(1 for e in ind_entries if e.is_met() is False),
            'no_data': sum(1 for e in ind_entries if e.is_met() is None),
            'entries': ind_entries,
            'percentage': round((met_count / ind_entries.count() * 100) if ind_entries.count() > 0 else 0)
        }
    
    total_entries = entries.count()
    total_met = sum(1 for e in entries if e.is_met() is True)
    total_not_met = sum(1 for e in entries if e.is_met() is False)
    total_no_data = sum(1 for e in entries if e.is_met() is None)
    
    # Get available filters
    quarters = Quarter.objects.filter(is_active=True)
    counties = County.objects.filter(is_active=True)
    if is_county_user:
        counties = user.counties.all()
    
    context = {
        'area': area,
        'indicators': indicators,
        'indicator_performance': indicator_performance,
        'total_entries': total_entries,
        'total_met': total_met,
        'total_not_met': total_not_met,
        'total_no_data': total_no_data,
        'quarters': quarters,
        'counties': counties,
        'selected_quarter': quarter_id,
        'selected_county': county_id,
        'user_role': user.role.get_display_name() if user.role else 'No Role',
    }
    return render(request, 'reports/thematic.html', context)


# ============================================
# SDG REPORT - Uses database permissions
# ============================================

@login_required
@view_reports_required
def sdg_report(request):
    """SDG Indicators Report - FULLY DATABASE DRIVEN"""
    user = request.user
    is_county_user = user.has_permission('manage_county_data') and user.is_county_user
    
    # SDG-related indicators
    sdg_indicators = Indicator.objects.filter(
        Q(code__startswith='FERT-') | 
        Q(code__startswith='MM-') |
        Q(code__startswith='PHED-'),
        is_active=True
    )
    
    quarter_id = request.GET.get('quarter')
    county_id = request.GET.get('county')
    
    # Build query - APPROVED ONLY
    query = Q(indicator__in=sdg_indicators, status='approved')
    if quarter_id:
        query &= Q(quarter_id=quarter_id)
    if county_id:
        if is_county_user and not user.counties.filter(id=county_id).exists():
            messages.error(request, 'You do not have permission to view data for this county.')
            return redirect('reports:sdg_report')
        query &= Q(county_id=county_id)
    elif is_county_user:
        query &= Q(county__in=user.counties.all())
    
    entries = DataEntry.objects.filter(query).select_related('county', 'quarter', 'indicator')
    
    # Group by SDG goal
    sdg_mapping = {
        'FERT': {'goal': 'SDG 3 & 5', 'description': 'Good Health & Gender Equality'},
        'MM': {'goal': 'SDG 3', 'description': 'Good Health and Well-being'},
        'PHED': {'goal': 'SDG 11 & 13', 'description': 'Sustainable Cities & Climate Action'},
    }
    
    sdg_performance = {}
    for area_code, info in sdg_mapping.items():
        area_indicators = sdg_indicators.filter(thematic_area__code=area_code)
        area_entries = entries.filter(indicator__in=area_indicators)
        met_count = sum(1 for e in area_entries if e.is_met() is True)
        total = area_entries.count()
        not_met = sum(1 for e in area_entries if e.is_met() is False)
        no_data = sum(1 for e in area_entries if e.is_met() is None)
        
        percentage = round((met_count / total * 100) if total > 0 else 0)
        not_met_percentage = round((not_met / total * 100) if total > 0 else 0)
        
        sdg_performance[area_code] = {
            'goal': info['goal'],
            'description': info['description'],
            'indicators': area_indicators.count(),
            'total': total,
            'met': met_count,
            'not_met': not_met,
            'no_data': no_data,
            'percentage': percentage,
            'not_met_percentage': not_met_percentage,
        }
    
    total_entries = entries.count()
    total_met = sum(1 for e in entries if e.is_met() is True)
    
    # Get available filters
    quarters = Quarter.objects.filter(is_active=True)
    counties = County.objects.filter(is_active=True)
    if is_county_user:
        counties = user.counties.all()
    
    context = {
        'sdg_performance': sdg_performance,
        'total_entries': total_entries,
        'total_met': total_met,
        'overall_percentage': round((total_met / total_entries * 100) if total_entries > 0 else 0),
        'quarters': quarters,
        'counties': counties,
        'selected_quarter': quarter_id,
        'selected_county': county_id,
        'user_role': user.role.get_display_name() if user.role else 'No Role',
    }
    return render(request, 'reports/sdg_report.html', context)


# ============================================
# PENDING REPORTS - Uses database permissions
# ============================================

@login_required
@permission_required('can_approve_data')
def pending_reports(request):
    """View pending approvals summary - For users with approval permission only"""
    user = request.user
    
    pending_entries = DataEntry.objects.filter(status='submitted').select_related('county', 'quarter', 'indicator')
    
    # If county user, only show their county
    if user.has_permission('manage_county_data') and user.is_county_user:
        pending_entries = pending_entries.filter(county__in=user.counties.all())
    
    # Group by county
    county_pending = {}
    for entry in pending_entries:
        county_name = entry.county.name
        if county_name not in county_pending:
            county_pending[county_name] = {
                'count': 0,
                'entries': []
            }
        county_pending[county_name]['count'] += 1
        county_pending[county_name]['entries'].append(entry)
    
    # Group by quarter
    quarter_pending = {}
    for entry in pending_entries:
        quarter_name = entry.quarter.name
        if quarter_name not in quarter_pending:
            quarter_pending[quarter_name] = {
                'count': 0,
                'entries': []
            }
        quarter_pending[quarter_name]['count'] += 1
        quarter_pending[quarter_name]['entries'].append(entry)
    
    context = {
        'pending_entries': pending_entries,
        'county_pending': county_pending,
        'quarter_pending': quarter_pending,
        'total_pending': pending_entries.count(),
    }
    return render(request, 'reports/pending.html', context)


# ============================================
# EXPORT FUNCTIONS - Uses database permissions
# ============================================

@login_required
@view_reports_required
def export_report(request, format):
    """Export report in specified format - FULLY DATABASE DRIVEN"""
    user = request.user
    is_county_user = user.has_permission('manage_county_data') and user.is_county_user
    
    county_id = request.GET.get('county')
    quarter_id = request.GET.get('quarter')
    thematic_area_id = request.GET.get('thematic_area')
    
    query = Q(status='approved')
    if county_id:
        if is_county_user and not user.counties.filter(id=county_id).exists():
            messages.error(request, 'You do not have permission to export data for this county.')
            return redirect('reports:export_data')
        query &= Q(county_id=county_id)
    if quarter_id:
        query &= Q(quarter_id=quarter_id)
    if thematic_area_id:
        indicators = Indicator.objects.filter(thematic_area_id=thematic_area_id)
        query &= Q(indicator__in=indicators)
    
    # RBAC: County users only see their county
    if is_county_user:
        query &= Q(county__in=user.counties.all())
    
    entries = DataEntry.objects.filter(query).select_related('county', 'quarter', 'indicator')
    
    if format == 'csv':
        return export_csv(entries)
    elif format == 'json':
        return export_json(entries)
    else:
        return HttpResponse("Unsupported format", status=400)


def export_csv(entries):
    """Export entries as CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['County', 'Quarter', 'Indicator Code', 'Indicator Name', 'Value', 'Unit', 'Target', 'Status', 'Met Target'])
    
    for entry in entries:
        writer.writerow([
            entry.county.name,
            entry.quarter.name,
            entry.indicator.code,
            entry.indicator.name,
            entry.value or 'No Data',
            entry.indicator.unit,
            entry.indicator.target_value or 'N/A',
            entry.get_status_display(),
            'Yes' if entry.is_met() is True else 'No' if entry.is_met() is False else 'N/A'
        ])
    
    return response


def export_json(entries):
    """Export entries as JSON"""
    data = []
    for entry in entries:
        data.append({
            'county': entry.county.name,
            'quarter': entry.quarter.name,
            'indicator_code': entry.indicator.code,
            'indicator_name': entry.indicator.name,
            'value': entry.value or 'No Data',
            'unit': entry.indicator.unit,
            'target': str(entry.indicator.target_value) if entry.indicator.target_value else 'N/A',
            'status': entry.get_status_display(),
            'met_target': entry.is_met() is True,
            'submitted_at': entry.submitted_at.isoformat() if entry.submitted_at else None,
        })
    
    return JsonResponse(data, safe=False)


# ============================================
# EXPORT DATA PAGE - Uses database permissions
# ============================================

@login_required
@view_reports_required
def export_data(request):
    """Main export page with options - FULLY DATABASE DRIVEN"""
    user = request.user
    is_county_user = user.has_permission('manage_county_data') and user.is_county_user
    can_view_all = user.is_superuser or user.has_any_permission(
        'can_approve_data', 
        'can_manage_indicators',
        'view_county_data'
    )
    
    # Get data for filters
    counties = County.objects.filter(is_active=True)
    quarters = Quarter.objects.filter(is_active=True)
    thematic_areas = ThematicArea.objects.all()
    indicators = Indicator.objects.filter(is_active=True)
    
    # Check rate limit
    allowed, remaining = rate_limit_check(user, 'export_page', max_per_hour=1000)
    if not allowed:
        messages.warning(request, 'You have exceeded the export limit.')
    else:
        messages.info(request, f'Export quota remaining this hour: {remaining}')
    
    # ===== RBAC USING DATABASE PERMISSIONS =====
    if is_county_user:
        counties = user.counties.all()
        # Only show indicators that have data for this county
        county_entries = DataEntry.objects.filter(county__in=counties, status='approved')
        indicators = indicators.filter(
            id__in=county_entries.values_list('indicator_id', flat=True).distinct()
        )
        thematic_areas = thematic_areas.filter(
            id__in=indicators.values_list('thematic_area_id', flat=True).distinct()
        )
    elif not can_view_all:
        counties = County.objects.none()
        indicators = Indicator.objects.none()
        thematic_areas = ThematicArea.objects.none()
    
    context = {
        'counties': counties,
        'quarters': quarters,
        'thematic_areas': thematic_areas,
        'indicators': indicators,
        'is_county_user': is_county_user,
    }
    return render(request, 'reports/export.html', context)


# ============================================
# EXPORT EXCEL - Uses database permissions
# ============================================

@login_required
@view_reports_required
def export_excel(request):
    """Export data to Excel with formatting - FULLY DATABASE DRIVEN"""
    user = request.user
    is_county_user = user.has_permission('manage_county_data') and user.is_county_user
    
    # Check rate limit
    allowed, remaining = rate_limit_check(user, 'excel')
    if not allowed:
        messages.error(request, 'Export limit exceeded. Max 100 exports per hour.')
        return redirect('reports:export_data')
    
    # Get filters from request
    county_id = request.GET.get('county')
    quarter_id = request.GET.get('quarter')
    thematic_area_id = request.GET.get('thematic_area')
    indicator_id = request.GET.get('indicator')
    export_type = request.GET.get('type', 'entries')
    
    # Log export request
    audit_log_export(user, 'excel', {
        'county_id': county_id,
        'quarter_id': quarter_id,
        'thematic_area_id': thematic_area_id,
        'indicator_id': indicator_id
    })
    
    # Build query
    query = Q()
    if county_id:
        if is_county_user and not user.counties.filter(id=county_id).exists():
            messages.error(request, 'You do not have permission to export data for this county.')
            return redirect('reports:export_data')
        query &= Q(county_id=county_id)
    if quarter_id:
        query &= Q(quarter_id=quarter_id)
    if thematic_area_id:
        indicators = Indicator.objects.filter(thematic_area_id=thematic_area_id)
        query &= Q(indicator__in=indicators)
    if indicator_id:
        query &= Q(indicator_id=indicator_id)
    
    # RBAC
    if is_county_user:
        query &= Q(county__in=user.counties.all())
    
    # Get entries
    entries = DataEntry.objects.filter(query).select_related('county', 'quarter', 'indicator')
    
    # Create workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Data Export"
    
    # Style definitions
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1a5632", end_color="1a5632", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Headers
    headers = ['County', 'Quarter', 'Indicator Code', 'Indicator Name', 'Thematic Area', 
               'Value', 'Unit', 'Target', 'Status', 'Met Target', 'Submitted By', 'Submitted At']
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border
    
    # Data rows
    for row, entry in enumerate(entries, 2):
        ws.cell(row=row, column=1, value=entry.county.name)
        ws.cell(row=row, column=2, value=entry.quarter.name)
        ws.cell(row=row, column=3, value=entry.indicator.code)
        ws.cell(row=row, column=4, value=entry.indicator.name)
        ws.cell(row=row, column=5, value=entry.indicator.thematic_area.name)
        ws.cell(row=row, column=6, value=entry.value or 'No Data')
        ws.cell(row=row, column=7, value=entry.indicator.unit)
        ws.cell(row=row, column=8, value=float(entry.indicator.target_value) if entry.indicator.target_value else 'N/A')
        ws.cell(row=row, column=9, value=entry.get_status_display())
        
        met_cell = ws.cell(row=row, column=10)
        if entry.is_met() is True:
            met_cell.value = 'Yes'
            met_cell.fill = PatternFill(start_color="e8f5e9", end_color="e8f5e9", fill_type="solid")
        elif entry.is_met() is False:
            met_cell.value = 'No'
            met_cell.fill = PatternFill(start_color="ffebee", end_color="ffebee", fill_type="solid")
        else:
            met_cell.value = 'N/A'
        
        ws.cell(row=row, column=11, value=entry.submitted_by.username if entry.submitted_by else '')
        ws.cell(row=row, column=12, value=entry.submitted_at.strftime('%Y-%m-%d %H:%M') if entry.submitted_at else '')
    
    # Auto-adjust column widths
    for col in range(1, len(headers) + 1):
        column_letter = get_column_letter(col)
        ws.column_dimensions[column_letter].width = 18
    
    # Create response
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
    wb.save(response)
    return response


# ============================================
# EXPORT INDICATORS - Uses database permissions
# ============================================

@login_required
@view_reports_required
def export_indicators(request):
    """Export indicators to Excel - FULLY DATABASE DRIVEN"""
    user = request.user
    
    # Check if user has permission to view indicators
    if not user.has_module_permission('indicators', 'view'):
        messages.error(request, 'You do not have permission to export indicators.')
        return redirect('reports:export_data')
    
    indicators = Indicator.objects.filter(is_active=True).select_related('thematic_area')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Indicators"
    
    # Headers
    headers = ['Code', 'Name', 'Thematic Area', 'Type', 'Data Type', 'Unit', 'Target', 'Source', 'Frequency']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="1a5632", end_color="1a5632", fill_type="solid")
        cell.font = Font(bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center")
    
    # Data
    for row, ind in enumerate(indicators, 2):
        ws.cell(row=row, column=1, value=ind.code)
        ws.cell(row=row, column=2, value=ind.name)
        ws.cell(row=row, column=3, value=ind.thematic_area.name)
        ws.cell(row=row, column=4, value=ind.get_indicator_type_display())
        ws.cell(row=row, column=5, value=ind.get_data_type_display())
        ws.cell(row=row, column=6, value=ind.unit)
        ws.cell(row=row, column=7, value=float(ind.target_value) if ind.target_value else '')
        ws.cell(row=row, column=8, value=ind.source_system)
        ws.cell(row=row, column=9, value=ind.get_frequency_display())
    
    # Auto-adjust
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 18
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="indicators_{datetime.now().strftime("%Y%m%d")}.xlsx"'
    wb.save(response)
    return response


# ============================================
# IMPORT INDICATORS - Uses database permissions
# ============================================

@login_required
@permission_required('can_manage_indicators')
def import_indicators(request):
    """Import indicators from Excel/CSV - FULLY DATABASE DRIVEN"""
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('reports:export_data')
    
    if 'file' not in request.FILES:
        messages.error(request, 'No file uploaded.')
        return redirect('reports:export_data')
    
    file = request.FILES['file']
    filename = file.name.lower()
    
    try:
        import csv
        import io
        from openpyxl import load_workbook
        
        # Read the file
        if filename.endswith('.csv'):
            decoded = file.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(decoded))
            data = list(reader)
        elif filename.endswith(('.xlsx', '.xls')):
            wb = load_workbook(file)
            ws = wb.active
            # Get headers from first row
            headers = []
            for cell in ws[1]:
                headers.append(cell.value)
            
            data = []
            for row in ws.iter_rows(min_row=2, values_only=True):
                if any(row):
                    row_dict = {}
                    for i, header in enumerate(headers):
                        if i < len(row):
                            row_dict[header] = row[i]
                    data.append(row_dict)
        else:
            messages.error(request, 'Unsupported file format. Please upload CSV or Excel.')
            return redirect('reports:export_data')
        
        # Process data
        imported = 0
        updated = 0
        errors = 0
        error_messages = []
        
        # Thematic area mapping
        thematic_map = {
            'FERT': 'Fertility',
            'MM': 'Morbidity & Mortality',
            'MIG': 'Migration & Urbanization',
            'PHED': 'Population, Health, Environment & Disaster'
        }
        
        for row in data:
            try:
                # Clean and get values - handle None values
                def get_value(key, default=''):
                    val = row.get(key)
                    if val is None:
                        return default
                    return str(val).strip()
                
                code = get_value('Code')
                name = get_value('Name')
                thematic_code = get_value('Thematic Area').upper()
                
                if not code or not name:
                    errors += 1
                    error_messages.append(f"Missing code or name")
                    continue
                
                # Get thematic area
                thematic_area = ThematicArea.objects.filter(code=thematic_code).first()
                if not thematic_area:
                    thematic_name = thematic_map.get(thematic_code, '')
                    thematic_area = ThematicArea.objects.filter(name__iexact=thematic_name).first()
                
                if not thematic_area:
                    errors += 1
                    error_messages.append(f"Thematic area not found: {thematic_code}")
                    continue
                
                # Helper to safely get numeric values
                def get_numeric(val):
                    if val is None or str(val).strip() == '':
                        return None
                    try:
                        return float(str(val).strip())
                    except ValueError:
                        return None
                
                # Helper to get string values
                def get_str(val):
                    if val is None:
                        return ''
                    return str(val).strip()
                
                # Check if exists
                if Indicator.objects.filter(code=code).exists():
                    indicator = Indicator.objects.get(code=code)
                    indicator.name = name
                    indicator.thematic_area = thematic_area
                    indicator.indicator_type = get_str(row.get('Type', 'output'))
                    indicator.data_type = get_str(row.get('Data Type', 'numeric'))
                    indicator.unit = get_str(row.get('Unit'))
                    indicator.target_value = get_numeric(row.get('Target'))
                    indicator.source_system = get_str(row.get('Source'))
                    indicator.frequency = get_str(row.get('Frequency', 'annual'))
                    indicator.min_value = get_numeric(row.get('Min Value'))
                    indicator.max_value = get_numeric(row.get('Max Value'))
                    indicator.description = get_str(row.get('Description'))
                    indicator.save()
                    updated += 1
                else:
                    Indicator.objects.create(
                        code=code,
                        name=name,
                        thematic_area=thematic_area,
                        indicator_type=get_str(row.get('Type', 'output')),
                        data_type=get_str(row.get('Data Type', 'numeric')),
                        unit=get_str(row.get('Unit')),
                        target_value=get_numeric(row.get('Target')),
                        source_system=get_str(row.get('Source')),
                        frequency=get_str(row.get('Frequency', 'annual')),
                        min_value=get_numeric(row.get('Min Value')),
                        max_value=get_numeric(row.get('Max Value')),
                        description=get_str(row.get('Description')),
                        created_by=request.user,
                    )
                    imported += 1
            except Exception as e:
                errors += 1
                error_messages.append(str(e))
        
        if imported > 0:
            messages.success(request, f'Imported {imported} new indicators.')
        if updated > 0:
            messages.success(request, f'Updated {updated} existing indicators.')
        if errors > 0:
            messages.error(request, f'{errors} errors occurred.')
            for msg in error_messages[:5]:
                messages.warning(request, msg)
        
        if imported == 0 and updated == 0 and errors == 0:
            messages.warning(request, 'No indicators were imported. Please check your file format.')
        
    except Exception as e:
        messages.error(request, f'Error processing file: {str(e)}')
    
    return redirect('reports:export_data')


# ============================================
# DOWNLOAD TEMPLATES - Uses database permissions
# ============================================

@login_required
def download_template(request, template_type):
    """Download import template for different data types - FULLY DATABASE DRIVEN"""
    user = request.user
    
    # Check permissions based on template type
    if template_type == 'indicators' and not user.has_permission('can_manage_indicators'):
        messages.error(request, 'You do not have permission to download indicator templates.')
        return redirect('reports:export_data')
    
    if template_type in ['partners', 'projects'] and not user.has_permission('manage_partners'):
        messages.error(request, 'You do not have permission to download partner templates.')
        return redirect('reports:export_data')
    
    if template_type == 'data_entries' and not user.has_module_permission('data_entry', 'add'):
        messages.error(request, 'You do not have permission to download data entry templates.')
        return redirect('reports:export_data')
    
    if template_type == 'indicators':
        return download_indicators_template()
    elif template_type == 'data_entries':
        return download_data_entries_template()
    elif template_type == 'partners':
        return download_partners_template()
    elif template_type == 'projects':
        return download_projects_template()
    else:
        messages.error(request, 'Invalid template type.')
        return redirect('reports:export_data')


def download_indicators_template():
    """Download template for importing indicators"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Indicators Template"
    
    # Define styles
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1a5632", end_color="1a5632", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Headers with descriptions
    headers = [
        ('Code*', 'Unique indicator code e.g., FERT-01'),
        ('Name*', 'Full indicator name'),
        ('Thematic Area*', 'FERT, MM, MIG, or PHED'),
        ('Type', 'impact, outcome, output, or action'),
        ('Data Type', 'numeric, percentage, decimal, boolean, or count'),
        ('Unit', 'e.g., %, per 100,000'),
        ('Target', 'Target value'),
        ('Source', 'Data source e.g., KNBS'),
        ('Frequency', 'annual, quarterly, monthly, 5_years, 10_years'),
        ('Min Value', 'Minimum allowed value'),
        ('Max Value', 'Maximum allowed value'),
        ('Description', 'Brief description')
    ]
    
    # Add headers
    for col, (header, comment) in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border
    
    # Add sample data
    samples = [
        ['FERT-01', 'Human Development Index', 'FERT', 'impact', 'decimal', 'Index (0-1)', '0.70', 'UNDP', 'annual', '0', '1', 'Composite index of human development'],
        ['FERT-02', 'Population Growth Rate', 'FERT', 'outcome', 'percentage', '%', '2.0', 'KNBS', 'annual', '0', '5', 'Annual population growth rate'],
        ['FERT-03', 'Total Fertility Rate (National)', 'FERT', 'outcome', 'decimal', 'Births per woman', '3.0', 'KNBS', '5_years', '0', '8', 'Average number of children per woman'],
        ['MM-01', 'Life Expectancy at Birth', 'MM', 'outcome', 'numeric', 'Years', '70', 'KNBS', 'annual', '40', '85', 'Average life expectancy'],
        ['MM-02', 'Maternal Mortality Ratio', 'MM', 'output', 'numeric', 'Per 100,000', '70', 'MOH', 'annual', '0', '1000', 'Maternal deaths per 100,000 live births'],
        ['MIG-01', 'Migration Rate', 'MIG', 'outcome', 'percentage', '%', '', 'KNBS', 'annual', '0', '100', 'Rate of population migration'],
        ['PHED-01', 'Disaster & Climate Change Mortality Rate', 'PHED', 'outcome', 'numeric', 'Per 100,000', '', 'NDOC', 'annual', '0', '1000', 'Mortality rate related to disasters'],
    ]
    
    # Add sample data rows
    for row, data in enumerate(samples, 2):
        for col, value in enumerate(data, 1):
            cell = ws.cell(row=row, column=col, value=value)
            cell.border = thin_border
    
    # Auto-adjust column widths
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 22
    
    # Create response
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="indicators_import_template.xlsx"'
    wb.save(response)
    return response


# Cross-module report catalogue
REPORT_CATALOGUE = {
    'data-entries': {
        'title': 'M&E Data Entries', 'module': 'Core M&E', 'icon': 'table',
        'description': 'Approved indicator values by county and reporting period.',
        'columns': ['County', 'Quarter', 'Indicator Code', 'Indicator', 'Value', 'Unit', 'Target', 'Met Target'],
    },
    'sdg-progress': {
        'title': 'SDG Progress', 'module': 'Indicators', 'icon': 'globe2',
        'description': 'Approved indicator performance grouped by SDG.',
        'columns': ['SDG', 'Indicator Code', 'Indicator', 'County', 'Quarter', 'Value', 'Target', 'Met Target'],
    },
    'field-visits': {
        'title': 'Field Visit Register', 'module': 'Field Monitoring', 'icon': 'clipboard2-pulse',
        'description': 'Field monitoring visits, locations, dates, and approval status.',
        'columns': ['Report Code', 'Organization', 'County', 'Visit Date', 'Status', 'Compiled By'],
    },
    'icpd-plan': {
        'title': 'ICPD Implementation Plan', 'module': 'ICPD', 'icon': 'diagram-3',
        'description': 'Commitments, objectives, activities, budgets, and accountability.',
        'columns': ['Commitment', 'Objective', 'Activity', 'Timeline', 'Responsibility', 'Budget'],
    },
    'icpd-performance': {
        'title': 'ICPD Annual Performance', 'module': 'ICPD', 'icon': 'bar-chart-line',
        'description': 'ICPD indicator baselines, targets, achievements, and status by financial year.',
        'columns': ['Financial Year', 'Indicator Code', 'Indicator', 'Baseline', 'Target', 'Achievement', 'Status'],
    },
    'icpd-comprehensive': {
        'title': 'Comprehensive ICPD Implementation Report', 'module': 'ICPD', 'icon': 'clipboard-data',
        'description': 'Complete commitment plan, budget, annual targets, achievements, expenditure, and remarks.',
        'columns': ['Commitment', 'Objective', 'Activity', 'Timeline', 'Responsibility', 'Budget (KES million)', 'Financial Year', 'Activity Indicator', 'Baseline', 'Baseline Year', 'Target', 'Achievement', 'Cumulative Target', 'Cumulative Achievement', 'Actual Expenditure (KES million)', 'Remarks'],
    },
    'icpd-narratives': {
        'key': 'icpd-narratives', 'title': 'ICPD Commitment Narratives', 'module': 'ICPD', 'icon': 'journal-text',
        'description': 'Saved commitment implementation narratives submitted by assigned contributors.',
        'columns': ['Commitment', 'Financial Year', 'Author', 'Last Updated'],
    },
    'partners': {
        'title': 'Partner Register', 'module': 'Partners', 'icon': 'people',
        'description': 'Partner profile, type, status, and county coverage.',
        'columns': ['Code', 'Partner', 'Type', 'Status', 'Counties', 'Contact Person', 'Email'],
    },
    'projects': {
        'title': 'Project Portfolio', 'module': 'Partners', 'icon': 'folder2-open',
        'description': 'Projects, delivery dates, budgets, expenditure, and progress.',
        'columns': ['Code', 'Project', 'Partner', 'Status', 'Start Date', 'End Date', 'Budget', 'Expenditure', 'Progress'],
    },
}


def _user_can_access_report(user, report_key):
    """Return whether a user is included in a report's optional access policy."""
    if user.is_superuser:
        return True

    policy = ReportAccessPolicy.objects.filter(
        report_key=report_key,
        is_restricted=True,
    ).first()
    if not policy:
        return True

    return (
        policy.allowed_users.filter(pk=user.pk).exists()
        or (user.role_id and policy.allowed_roles.filter(pk=user.role_id).exists())
    )


@login_required
@permission_required('change_reports')
def report_access(request):
    """Allow report managers to select the roles and users for each report."""
    if request.method == 'POST':
        roles = Role.objects.filter(is_active=True)
        users = User.objects.filter(is_active=True, is_verified=True)

        for report_key in REPORT_CATALOGUE:
            policy, _ = ReportAccessPolicy.objects.get_or_create(report_key=report_key)
            policy.is_restricted = request.POST.get(f'restricted_{report_key}') == 'on'
            policy.save()
            policy.allowed_roles.set(roles.filter(pk__in=request.POST.getlist(f'roles_{report_key}')))
            policy.allowed_users.set(users.filter(pk__in=request.POST.getlist(f'users_{report_key}')))

        messages.success(request, 'Report access settings updated.')
        return redirect('reports:report_access')

    policies = {
        policy.report_key: policy
        for policy in ReportAccessPolicy.objects.prefetch_related('allowed_roles', 'allowed_users')
    }
    report_access_settings = []
    for report_key, report in REPORT_CATALOGUE.items():
        policy = policies.get(report_key)
        report_access_settings.append({
            'key': report_key,
            'report': report,
            'is_restricted': policy.is_restricted if policy else False,
            'allowed_role_ids': list(policy.allowed_roles.values_list('id', flat=True)) if policy else [],
            'allowed_user_ids': list(policy.allowed_users.values_list('id', flat=True)) if policy else [],
        })

    return render(request, 'reports/access.html', {
        'report_access_settings': report_access_settings,
        'roles': Role.objects.filter(is_active=True).order_by('display_name', 'name'),
        'users': User.objects.filter(is_active=True, is_verified=True).select_related('role').order_by('username'),
    })


def _report_scope(request):
    """Return the requester's authoritative county queryset, if any."""
    return request.user.counties.all() if request.user.is_county_user else None


def _icpd_report_filters(request):
    """Build the ICPD hierarchy filter querysets from the selected report filters."""
    from icpd.models import Activity, ActivityIndicator, Commitment, Objective

    commitment_ids = request.GET.getlist('commitment')
    objective_ids = request.GET.getlist('objective')
    activity_ids = request.GET.getlist('activity')
    indicator_ids = request.GET.getlist('activity_indicator')
    financial_years = request.GET.getlist('financial_year')

    commitments = Commitment.objects.filter(is_active=True)
    objectives = Objective.objects.filter(commitment_id__in=commitment_ids) if commitment_ids else Objective.objects.all()
    activities = Activity.objects.filter(objective_id__in=objective_ids) if objective_ids else Activity.objects.filter(
        objective__commitment_id__in=commitment_ids,
    ) if commitment_ids else Activity.objects.all()
    indicators = ActivityIndicator.objects.filter(activity_id__in=activity_ids) if activity_ids else ActivityIndicator.objects.filter(
        activity__objective_id__in=objective_ids,
    ) if objective_ids else ActivityIndicator.objects.filter(
        activity__objective__commitment_id__in=commitment_ids,
    ) if commitment_ids else ActivityIndicator.objects.all()

    return {
        'commitment_ids': commitment_ids,
        'objective_ids': objective_ids,
        'activity_ids': activity_ids,
        'indicator_ids': indicator_ids,
        'financial_years': financial_years,
        'commitments': commitments,
        'objectives': objectives,
        'activities': activities,
        'indicators': indicators,
    }


def _report_rows(report_key, request):
    county = _report_scope(request)
    county_ids = request.GET.getlist('county')
    if county:
        county_ids = [str(county.id)]
    quarter_ids = request.GET.getlist('quarter')

    if report_key == 'data-entries':
        entries = DataEntry.objects.filter(status='approved').select_related('county', 'quarter', 'indicator')
        if county_ids:
            entries = entries.filter(county_id__in=county_ids)
        if quarter_ids:
            entries = entries.filter(quarter_id__in=quarter_ids)
        return [[entry.county.name, entry.quarter.name, entry.indicator.code, entry.indicator.name,
                 entry.value or '', entry.indicator.unit, entry.target_at_submission or '',
                 'Yes' if entry.is_met() is True else 'No' if entry.is_met() is False else 'N/A'] for entry in entries]

    if report_key == 'sdg-progress':
        entries = DataEntry.objects.filter(status='approved', indicator__sdgs__isnull=False).select_related(
            'county', 'quarter', 'indicator').prefetch_related('indicator__sdgs').distinct()
        if county_ids:
            entries = entries.filter(county_id__in=county_ids)
        if quarter_ids:
            entries = entries.filter(quarter_id__in=quarter_ids)
        return [[', '.join(f'SDG {sdg.number}' for sdg in entry.indicator.sdgs.all()), entry.indicator.code,
                 entry.indicator.name, entry.county.name, entry.quarter.name, entry.value or '',
                 entry.target_at_submission or '', 'Yes' if entry.is_met() is True else 'No' if entry.is_met() is False else 'N/A'] for entry in entries]

    if report_key == 'field-visits':
        from field_monitoring.models import FieldVisitReport
        visits = FieldVisitReport.objects.select_related('county', 'report_compiled_by')
        if county_ids:
            visits = visits.filter(county_id__in=county_ids)
        return [[visit.report_code, visit.organization_name, visit.county.name, visit.visit_date,
                 visit.get_status_display(), visit.report_compiled_by.get_full_name() if visit.report_compiled_by else ''] for visit in visits]

    if report_key == 'icpd-plan':
        from icpd.models import Activity
        filters = _icpd_report_filters(request)
        activities = Activity.objects.select_related('objective__commitment')
        if filters['commitment_ids']:
            activities = activities.filter(objective__commitment_id__in=filters['commitment_ids'])
        if filters['objective_ids']:
            activities = activities.filter(objective_id__in=filters['objective_ids'])
        if filters['activity_ids']:
            activities = activities.filter(pk__in=filters['activity_ids'])
        if filters['indicator_ids']:
            activities = activities.filter(activity_indicators__id__in=filters['indicator_ids'])
        return [[activity.objective.commitment.title, activity.objective.title, activity.title, activity.timeline,
                 activity.responsibility, f'{activity.budget_currency} {activity.budget_amount or 0}']
                for activity in activities.distinct()]

    if report_key == 'icpd-performance':
        from icpd.models import IndicatorYearData
        filters = _icpd_report_filters(request)
        year_data_rows = IndicatorYearData.objects.select_related('activity_indicator__activity__objective__commitment')
        if filters['commitment_ids']:
            year_data_rows = year_data_rows.filter(activity_indicator__activity__objective__commitment_id__in=filters['commitment_ids'])
        if filters['objective_ids']:
            year_data_rows = year_data_rows.filter(activity_indicator__activity__objective_id__in=filters['objective_ids'])
        if filters['activity_ids']:
            year_data_rows = year_data_rows.filter(activity_indicator__activity_id__in=filters['activity_ids'])
        if filters['indicator_ids']:
            year_data_rows = year_data_rows.filter(activity_indicator_id__in=filters['indicator_ids'])
        if filters['financial_years']:
            year_data_rows = year_data_rows.filter(financial_year__in=filters['financial_years'])
        return [[year_data.financial_year, year_data.activity_indicator.code,
             year_data.activity_indicator.name, year_data.activity_indicator.baseline_value or '',
                 year_data.target_value or '', year_data.achievement_value or '', year_data.get_status_display()]
                for year_data in year_data_rows]

    if report_key == 'icpd-comprehensive':
        from icpd.models import Activity, ActivityYearData, IndicatorYearData
        filters = _icpd_report_filters(request)
        activities = Activity.objects.select_related('objective__commitment').prefetch_related(
            'activity_indicators__yearly_data', 'yearly_expenditure',
        )
        if filters['commitment_ids']:
            activities = activities.filter(objective__commitment_id__in=filters['commitment_ids'])
        if filters['objective_ids']:
            activities = activities.filter(objective_id__in=filters['objective_ids'])
        if filters['activity_ids']:
            activities = activities.filter(pk__in=filters['activity_ids'])
        if filters['indicator_ids']:
            activities = activities.filter(activity_indicators__id__in=filters['indicator_ids']).distinct()

        rows = []
        for activity in activities:
            expenditures = {item.financial_year: item for item in activity.yearly_expenditure.all()}
            for indicator in activity.activity_indicators.all():
                year_data_rows = list(indicator.yearly_data.all())
                if filters['financial_years']:
                    year_data_rows = [item for item in year_data_rows if item.financial_year in filters['financial_years']]
                if not year_data_rows:
                    if not filters['financial_years']:
                        rows.append(_icpd_comprehensive_row(activity, indicator, None, None))
                    continue
                for year_data in year_data_rows:
                    rows.append(_icpd_comprehensive_row(
                        activity, indicator, year_data, expenditures.get(year_data.financial_year),
                    ))
            if not activity.activity_indicators.all() and not filters['indicator_ids'] and not filters['financial_years']:
                rows.append(_icpd_comprehensive_row(activity, None, None, None))
        return rows

    if report_key == 'icpd-narratives':
        from icpd.models import CommitmentNarrativeReport
        narratives = CommitmentNarrativeReport.objects.select_related('commitment', 'author').order_by(
            'commitment__sort_order', 'financial_year', 'author__username',
        )
        filters = _icpd_report_filters(request)
        if filters['commitment_ids']:
            narratives = narratives.filter(commitment_id__in=filters['commitment_ids'])
        if filters['financial_years']:
            narratives = narratives.filter(financial_year__in=filters['financial_years'])
        if not (request.user.is_superuser or request.user.is_admin_user):
            narratives = narratives.filter(
                Q(commitment__access_policy__isnull=True)
                | Q(commitment__access_policy__is_restricted=False)
                | Q(commitment__access_policy__allowed_users=request.user)
                | Q(commitment__access_policy__allowed_roles=request.user.role_id if request.user.role_id else None),
            ).distinct()
        return [
            [narrative.commitment.title, narrative.financial_year,
             narrative.author.get_full_name() or narrative.author.username,
             narrative.updated_at.strftime('%d %b %Y, %H:%M')]
            for narrative in narratives
            if _narrative_has_content(narrative)
        ]

    if report_key == 'partners':
        from partners.models import Partner
        partners = Partner.objects.prefetch_related('counties')
        if county_ids:
            partners = partners.filter(counties__id__in=county_ids).distinct()
        return [[partner.code, partner.name, partner.get_partner_type_display(), partner.get_status_display(),
                 ', '.join(partner.counties.values_list('name', flat=True)), partner.contact_person, partner.contact_email]
                for partner in partners]

    if report_key == 'projects':
        from partners.models import Project
        projects = Project.objects.select_related('partner').prefetch_related('counties', 'milestones')
        if county_ids:
            projects = projects.filter(counties__id__in=county_ids).distinct()
        return [[project.code, project.name, project.partner.name, project.get_status_display(), project.start_date,
                 project.end_date, project.budget, project.expenditure, f'{project.get_progress()}%'] for project in projects]

    raise KeyError(report_key)


def _icpd_comprehensive_row(activity, indicator, year_data, expenditure):
    return [
        activity.objective.commitment.title,
        activity.objective.title,
        activity.title,
        activity.timeline,
        activity.responsibility,
        activity.budget_amount if activity.budget_amount is not None else '',
        year_data.financial_year if year_data else '',
        f'{indicator.code} - {indicator.name}' if indicator else '',
        indicator.baseline_value if indicator and indicator.baseline_value is not None else '',
        indicator.baseline_year if indicator else '',
        year_data.target_value if year_data and year_data.target_value is not None else '',
        year_data.achievement_value if year_data and year_data.achievement_value is not None else '',
        indicator.cumulative_target_value if indicator and indicator.cumulative_target_value is not None else '',
        indicator.cumulative_achievement_value if indicator and indicator.cumulative_achievement_value is not None else '',
        expenditure.expenditure_amount if expenditure and expenditure.expenditure_amount is not None else '',
        year_data.remarks if year_data else '',
    ]


def _narrative_has_content(narrative):
    return any((
        narrative.introduction,
        narrative.executive_summary,
        narrative.abbreviations,
        narrative.other_actor_contributions,
        narrative.facilitating_factors,
        narrative.challenges,
        narrative.opportunities,
        narrative.conclusion_and_recommendations,
        narrative.references,
    ))


@login_required
@view_reports_required
def report_preview(request, report_key):
    report = get_object_or_404_placeholder(report_key)
    if not _user_can_access_report(request.user, report_key):
        messages.error(request, 'You do not have access to this report.')
        return redirect('reports:report_list')
    icpd_filters = _icpd_report_filters(request) if report_key.startswith('icpd-') else None
    icpd_financial_years = []
    if icpd_filters:
        from icpd.models import FINANCIAL_YEAR_CHOICES
        icpd_financial_years = FINANCIAL_YEAR_CHOICES
    narrative_entries = []
    if report_key == 'icpd-narratives':
        from icpd.models import CommitmentNarrativeReport
        narrative_entries = CommitmentNarrativeReport.objects.select_related('commitment', 'author').order_by(
            'commitment__sort_order', 'financial_year', 'author__username',
        )
        if icpd_filters['commitment_ids']:
            narrative_entries = narrative_entries.filter(commitment_id__in=icpd_filters['commitment_ids'])
        if icpd_filters['financial_years']:
            narrative_entries = narrative_entries.filter(financial_year__in=icpd_filters['financial_years'])
        if not (request.user.is_superuser or request.user.is_admin_user):
            narrative_entries = narrative_entries.filter(
                Q(commitment__access_policy__isnull=True)
                | Q(commitment__access_policy__is_restricted=False)
                | Q(commitment__access_policy__allowed_users=request.user)
                | Q(commitment__access_policy__allowed_roles=request.user.role_id if request.user.role_id else None),
            ).distinct()
        narrative_entries = [entry for entry in narrative_entries if _narrative_has_content(entry)]
        for entry in narrative_entries:
            entry.sections = (
                ('a. Introduction (1-2 paragraphs)', entry.introduction),
                ('b. Executive summary', entry.executive_summary),
                ('c. Abbreviations', entry.abbreviations),
                ('e. Contribution by other actors', entry.other_actor_contributions),
                ('f. Facilitating factors', entry.facilitating_factors),
                ('What challenges slowed progress?', entry.challenges),
                ('What opportunities to enhance implementation exist?', entry.opportunities),
                ('g. Conclusion and Recommendations', entry.conclusion_and_recommendations),
                ('h. References', entry.references),
            )

    return render(request, 'reports/preview.html', {
        'report': report,
        'rows': _report_rows(report_key, request),
        'counties': _report_scope(request) if _report_scope(request) else County.objects.filter(is_active=True),
        'quarters': Quarter.objects.filter(is_active=True),
        'selected_counties': [str(county_id) for county_id in request.user.counties.values_list('id', flat=True)] if _report_scope(request) else request.GET.getlist('county'),
        'selected_quarters': request.GET.getlist('quarter'),
        'icpd_filters': icpd_filters,
        'icpd_financial_years': icpd_financial_years,
        'narrative_entries': narrative_entries,
    })


def get_object_or_404_placeholder(report_key):
    try:
        return REPORT_CATALOGUE[report_key]
    except KeyError:
        from django.http import Http404
        raise Http404('Unknown report')


@login_required
@view_reports_required
def report_export(request, report_key, export_format):
    report = get_object_or_404_placeholder(report_key)
    if not _user_can_access_report(request.user, report_key):
        messages.error(request, 'You do not have access to this report.')
        return redirect('reports:report_list')
    rows = _report_rows(report_key, request)
    filename = report_key.replace('-', '_')
    if export_format == 'excel':
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = report['title'][:31]
        sheet.append(report['columns'])
        for row in rows:
            sheet.append(row)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(max(len(str(cell.value or '')) for cell in column) + 2, 45)
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        workbook.save(response)
        return response
    if export_format == 'pdf':
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Spacer, Paragraph, Table, TableStyle
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
        document = SimpleDocTemplate(response, pagesize=landscape(letter))
        table = Table([report['columns']] + [[str(value) for value in row] for row in rows], repeatRows=1)
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5632')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('GRID', (0, 0), (-1, -1), 0.25, colors.grey), ('FONTSIZE', (0, 0), (-1, -1), 7)]))
        document.build([Paragraph(report['title'], getSampleStyleSheet()['Title']), Spacer(1, 12), table])
        return response
    return HttpResponse('Unsupported export format.', status=400)


def download_data_entries_template():
    """Download template for importing data entries"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Data Entries Template"
    
    headers = [
        ('County*', 'County name exactly as in system'),
        ('Quarter*', 'Quarter name e.g., Q1 2025'),
        ('Indicator Code*', 'Indicator code e.g., FERT-01'),
        ('Value*', 'The actual data value'),
        ('Notes', 'Optional notes about this entry')
    ]
    
    for col, (header, comment) in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="1a5632", end_color="1a5632", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    # Sample data
    samples = [
        ['Nairobi', 'Q1 2025', 'FERT-01', '0.72', 'From census data'],
        ['Mombasa', 'Q1 2025', 'FERT-02', '2.5', ''],
        ['Kisumu', 'Q1 2025', 'MM-01', '68', ''],
    ]
    
    for row, data in enumerate(samples, 2):
        for col, value in enumerate(data, 1):
            ws.cell(row=row, column=col, value=value)
    
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 20
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="data_entries_import_template.xlsx"'
    wb.save(response)
    return response


def download_partners_template():
    """Download template for importing partners"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Partners Template"
    
    headers = [
        ('Code*', 'Unique partner code e.g., P-001'),
        ('Name*', 'Organization name'),
        ('Type', 'ngo, cbo, fbo, government, private, academic, development, other'),
        ('Contact Person*', 'Primary contact name'),
        ('Contact Email*', 'Email address'),
        ('Contact Phone', 'Phone number'),
        ('Address', 'Physical address'),
        ('Website', 'Website URL'),
        ('Status', 'active, inactive, pending, suspended'),
        ('Counties', 'Comma-separated county codes')
    ]
    
    for col, (header, comment) in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="1a5632", end_color="1a5632", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    samples = [
        ['P-001', 'Red Cross Kenya', 'ngo', 'John Doe', 'john@redcross.org', '+254-712-345-678', 'Nairobi', 'www.redcross.org', 'active', '001,047'],
        ['P-002', 'UNFPA Kenya', 'development', 'Jane Smith', 'jane@unfpa.org', '+254-712-345-679', 'Nairobi', 'www.unfpa.org', 'active', '001'],
    ]
    
    for row, data in enumerate(samples, 2):
        for col, value in enumerate(data, 1):
            ws.cell(row=row, column=col, value=value)
    
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 20
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="partners_import_template.xlsx"'
    wb.save(response)
    return response


def download_projects_template():
    """Download template for importing projects"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Projects Template"
    
    headers = [
        ('Code*', 'Unique project code e.g., PRJ-001'),
        ('Name*', 'Project name'),
        ('Partner Code*', 'Partner code this project belongs to'),
        ('Start Date*', 'YYYY-MM-DD format'),
        ('End Date*', 'YYYY-MM-DD format'),
        ('Budget', 'Total budget in KSh'),
        ('Status', 'planning, active, completed, suspended, cancelled'),
        ('Project Lead', 'Name of project lead'),
        ('Project Email', 'Project email'),
        ('Project Phone', 'Project phone'),
        ('Indicators', 'Comma-separated indicator codes'),
        ('Counties', 'Comma-separated county codes')
    ]
    
    for col, (header, comment) in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="1a5632", end_color="1a5632", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    samples = [
        ['PRJ-001', 'Population Health Project', 'P-001', '2025-01-01', '2025-12-31', '5000000', 'active', 'John Lead', 'project@example.com', '+254-712-345-678', 'FERT-01,MM-01', '001,047'],
        ['PRJ-002', 'Migration Study', 'P-002', '2025-02-01', '2025-10-31', '3000000', 'planning', 'Jane Lead', 'migration@example.com', '+254-712-345-679', 'MIG-01', '002'],
    ]
    
    for row, data in enumerate(samples, 2):
        for col, value in enumerate(data, 1):
            ws.cell(row=row, column=col, value=value)
    
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 20
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="projects_import_template.xlsx"'
    wb.save(response)
    return response