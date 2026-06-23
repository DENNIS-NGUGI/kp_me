from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_center, name='center'),
    path('mark-read/<int:pk>/', views.mark_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('mark-unread/<int:pk>/', views.mark_unread, name='mark_unread'),
    path('delete/<int:pk>/', views.delete_notification, name='delete'),
    path('clear-all/', views.clear_all, name='clear_all'),
    path('preferences/', views.preferences, name='preferences'),
    path('api/unread-count/', views.api_unread_count, name='api_unread_count'),
    path('api/notifications/', views.api_notifications, name='api_notifications'),
]
