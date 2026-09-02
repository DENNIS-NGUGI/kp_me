from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from .models import Notification, NotificationPreference

@login_required
def notification_center(request):
    """Main notification center"""
    user = request.user
    
    # Get notifications
    notifications = Notification.objects.filter(user=user).order_by('-created_at')
    unread_count = notifications.filter(is_read=False).count()
    
    # Filter by type
    filter_type = request.GET.get('type')
    if filter_type:
        notifications = notifications.filter(notification_type=filter_type)
    
    # Filter by read status
    read_filter = request.GET.get('read')
    if read_filter == 'unread':
        notifications = notifications.filter(is_read=False)
    elif read_filter == 'read':
        notifications = notifications.filter(is_read=True)
    
    # Pagination (simple - 20 per page)
    page = int(request.GET.get('page', 1))
    per_page = 20
    start = (page - 1) * per_page
    end = start + per_page
    total = notifications.count()
    notifications_page = notifications[start:end]
    
    context = {
        'notifications': notifications_page,
        'unread_count': unread_count,
        'total_count': total,
        'page': page,
        'total_pages': (total + per_page - 1) // per_page,
        'filter_type': filter_type,
        'read_filter': read_filter,
    }
    return render(request, 'notifications/center.html', context)


@login_required
def mark_read(request, pk):
    """Mark a single notification as read"""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    return redirect('notifications:center')


@login_required
def mark_all_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(user=request.user, is_read=False).update(
        is_read=True,
        read_at=timezone.now()
    )
    messages.success(request, 'All notifications marked as read.')
    return redirect('notifications:center')


@login_required
def mark_unread(request, pk):
    """Mark a notification as unread"""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.mark_as_unread()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    return redirect('notifications:center')


@login_required
def delete_notification(request, pk):
    """Delete a notification"""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    messages.success(request, 'Notification deleted.')
    return redirect('notifications:center')


@login_required
def clear_all(request):
    """Clear all notifications"""
    Notification.objects.filter(user=request.user).delete()
    messages.success(request, 'All notifications cleared.')
    return redirect('notifications:center')


@login_required
def preferences(request):
    """User notification preferences"""
    user = request.user
    prefs, created = NotificationPreference.objects.get_or_create(user=user)
    
    if request.method == 'POST':
        # Email preferences
        prefs.email_submissions = request.POST.get('email_submissions') == 'on'
        prefs.email_approvals = request.POST.get('email_approvals') == 'on'
        prefs.email_deadlines = request.POST.get('email_deadlines') == 'on'
        prefs.email_reminders = request.POST.get('email_reminders') == 'on'
        
        # In-app preferences
        prefs.in_app_submissions = request.POST.get('in_app_submissions') == 'on'
        prefs.in_app_approvals = request.POST.get('in_app_approvals') == 'on'
        prefs.in_app_deadlines = request.POST.get('in_app_deadlines') == 'on'
        prefs.in_app_reminders = request.POST.get('in_app_reminders') == 'on'
        
        prefs.save()
        messages.success(request, 'Notification preferences updated successfully.')
        return redirect('notifications:preferences')
    
    context = {'prefs': prefs}
    return render(request, 'notifications/preferences.html', context)


@login_required
def api_unread_count(request):
    """API endpoint for unread notification count"""
    if not request.user.is_authenticated:
        return JsonResponse({'count': 0})
    
    count = Notification.objects.filter(
        user=request.user, 
        is_read=False
    ).count()
    
    return JsonResponse({'count': count})


@login_required
def api_notifications(request):
    """API endpoint for recent notifications"""
    if not request.user.is_authenticated:
        return JsonResponse({'notifications': []})
    
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')[:10]
    
    data = []
    for n in notifications:
        data.append({
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'type': n.notification_type,
            'is_read': n.is_read,
            'created_at': n.created_at.strftime('%Y-%m-%d %H:%M'),
            'action_url': n.action_url,
            'action_text': n.action_text,
        })
    
    return JsonResponse({'notifications': data})
