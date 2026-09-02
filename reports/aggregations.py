"""
Optimized report aggregation functions using database queries
Replaces O(n) Python loops with database aggregation
"""

from django.db.models import Count, Case, When, Q, F, DecimalField
from django.db.models.functions import Cast
from data_entry.models import DataEntry
from indicators.models import Indicator
from django.core.cache import cache
from functools import wraps
import hashlib
import json


def cache_report_data(timeout=300):
    """
    Decorator to cache report data for 5 minutes (300 seconds)
    Generates cache key based on user and filters
    """
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Generate cache key based on user, filters, and function name
            user_key = f"user_{request.user.id}"
            filters_key = hashlib.md5(
                json.dumps(dict(request.GET.items()), sort_keys=True).encode()
            ).hexdigest()
            cache_key = f"{func.__name__}_{user_key}_{filters_key}"
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Call function and cache result
            result = func(request, *args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result
        return wrapper
    return decorator


def count_entries_met(queryset):
    """
    Optimized: Count entries where value >= target (using database aggregation)
    Replaces: for entry in entries: if entry.is_met() is True: count += 1
    
    Args:
        queryset: DataEntry queryset
    
    Returns:
        dict with 'met', 'not_met', and 'no_data' counts
    """
    # For most indicators: value >= target
    # For FERT-* (except FERT-01): value <= target
    # Returns None if value or target missing
    
    result = queryset.aggregate(
        # Count where value and target exist AND (value >= target OR fert-specific logic)
        met=Count(
            Case(
                When(
                    Q(value__isnull=False) & Q(target_at_submission__isnull=False),
                    then=Case(
                        # FERT indicators (except FERT-01): value <= target
                        When(
                            Q(indicator__code__startswith='FERT-') & 
                            ~Q(indicator__code='FERT-01') &
                            Q(value__lte=F('target_at_submission')),
                            then=1
                        ),
                        # Other indicators: value >= target
                        When(
                            ~Q(indicator__code__startswith='FERT-') & 
                            Q(value__gte=F('target_at_submission')),
                            then=1
                        ),
                        When(
                            Q(indicator__code='FERT-01') & 
                            Q(value__gte=F('target_at_submission')),
                            then=1
                        ),
                        default=None
                    )
                ),
                default=None
            )
        ),
        # Count where value and target exist but condition not met
        not_met=Count(
            Case(
                When(
                    Q(value__isnull=False) & Q(target_at_submission__isnull=False),
                    then=Case(
                        # FERT indicators (except FERT-01): value > target (not met)
                        When(
                            Q(indicator__code__startswith='FERT-') & 
                            ~Q(indicator__code='FERT-01') &
                            Q(value__gt=F('target_at_submission')),
                            then=1
                        ),
                        # Other indicators: value < target (not met)
                        When(
                            ~Q(indicator__code__startswith='FERT-') & 
                            Q(value__lt=F('target_at_submission')),
                            then=1
                        ),
                        When(
                            Q(indicator__code='FERT-01') & 
                            Q(value__lt=F('target_at_submission')),
                            then=1
                        ),
                        default=None
                    )
                ),
                default=None
            )
        ),
        # Count where value or target missing (no data)
        no_data=Count(
            Case(
                When(Q(value__isnull=True) | Q(target_at_submission__isnull=True), then=1),
                default=None
            )
        ),
    )
    
    return {
        'met': result['met'] or 0,
        'not_met': result['not_met'] or 0,
        'no_data': result['no_data'] or 0,
        'total': queryset.count()
    }


def get_thematic_performance(entries):
    """
    Optimized: Get performance by thematic area
    
    Args:
        entries: DataEntry queryset
    
    Returns:
        list of dicts with thematic area performance
    """
    from indicators.models import ThematicArea
    
    thematic_colors = {
        'Fertility': '#1a5632',
        'Morbidity & Mortality': '#b71c1c',
        'Migration & Urbanization': '#f39c12',
        'PHED': '#2d8a4e'
    }
    
    performance = []
    for area in ThematicArea.objects.all():
        area_indicators = Indicator.objects.filter(thematic_area=area, is_active=True)
        area_entries = entries.filter(indicator__in=area_indicators)
        
        if area_entries.count() == 0:
            continue  # Skip if no data
        
        counts = count_entries_met(area_entries)
        
        total = area_entries.count()
        met = counts['met']
        percentage = round((met / total * 100) if total > 0 else 0)
        
        performance.append({
            'name': area.name,
            'code': area.code,
            'total_indicators': area_indicators.count(),
            'total_entries': total,
            'met': met,
            'not_met': counts['not_met'],
            'no_data': counts['no_data'],
            'percentage': percentage,
            'color': thematic_colors.get(area.name, '#6c757d')
        })
    
    return performance


def get_quarterly_performance(entries):
    """
    Optimized: Get performance by quarter
    
    Args:
        entries: DataEntry queryset
    
    Returns:
        list of dicts with quarterly performance (last 8 quarters)
    """
    from core.models import Quarter
    
    quarters = Quarter.objects.filter(is_active=True).order_by('-start_date')[:8]
    
    quarterly_data = []
    for q in reversed(quarters):
        q_entries = entries.filter(quarter=q)
        
        if q_entries.count() == 0:
            q_total = 0
            q_met = 0
        else:
            counts = count_entries_met(q_entries)
            q_total = counts['total']
            q_met = counts['met']
        
        percentage = round((q_met / q_total * 100) if q_total > 0 else 0)
        
        quarterly_data.append({
            'name': q.name,
            'total': q_total,
            'met': q_met,
            'percentage': percentage
        })
    
    return quarterly_data


def get_county_performance(entries, counties):
    """
    Optimized: Get performance by county
    
    Args:
        entries: DataEntry queryset
        counties: County queryset
    
    Returns:
        list of dicts with county performance (top 10)
    """
    county_performance = []
    
    for county in counties:
        county_entries = entries.filter(county=county)
        
        if county_entries.count() == 0:
            continue
        
        counts = count_entries_met(county_entries)
        total = counts['total']
        met = counts['met']
        percentage = round((met / total * 100) if total > 0 else 0)
        
        county_performance.append({
            'name': county.name,
            'total': total,
            'met': met,
            'percentage': percentage
        })
    
    # Sort by percentage descending and limit to top 10
    county_performance.sort(key=lambda x: x['percentage'], reverse=True)
    return county_performance[:10]


def audit_log_export(user, export_type, filters=None):
    """
    Log data export for audit trail
    
    Args:
        user: User object
        export_type: 'csv', 'json', 'excel', 'pdf'
        filters: dict of filters applied
    """
    from django.utils import timezone
    import logging
    
    logger = logging.getLogger('data_export')
    
    log_data = {
        'user': user.username,
        'user_id': user.id,
        'export_type': export_type,
        'timestamp': timezone.now().isoformat(),
        'filters': filters or {}
    }
    
    logger.info(f"Data export: {user.username} exported {export_type}", extra=log_data)


def rate_limit_check(user, export_type, max_per_hour=100):
    """
    Check if user is within rate limit for exports
    
    Args:
        user: User object
        export_type: 'csv', 'json', 'excel', 'pdf'
        max_per_hour: Max exports per hour (default 100)
    
    Returns:
        tuple (allowed: bool, remaining: int)
    """
    from django.utils import timezone
    from datetime import timedelta
    
    cache_key = f"export_limit_{user.id}_{export_type}"
    current_count = cache.get(cache_key, 0)
    
    if current_count >= max_per_hour:
        return False, 0
    
    # Increment counter and set 1-hour expiry
    new_count = current_count + 1
    cache.set(cache_key, new_count, 3600)  # 3600 seconds = 1 hour
    
    remaining = max_per_hour - new_count
    return True, remaining
