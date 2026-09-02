"""
URL Configuration for Field Monitoring App
"""

from django.urls import path
from . import views

app_name = 'field_monitoring'

urlpatterns = [
    # Dashboard
    path('', views.field_monitoring_dashboard, name='dashboard'),
    path('dashboard/', views.field_monitoring_dashboard, name='dashboard_view'),
    
    # List
    path('reports/', views.field_visit_list, name='field_visit_list'),
    
    # CRUD Operations
    path('reports/create/', views.field_visit_create, name='field_visit_create'),
    path('reports/<int:pk>/', views.field_visit_detail, name='field_visit_detail'),
    path('reports/<int:pk>/edit/', views.field_visit_update, name='field_visit_update'),
    path('reports/<int:pk>/delete/', views.field_visit_delete, name='field_visit_delete'),
    
    # Status Actions
    path('reports/<int:pk>/submit/', views.field_visit_submit, name='field_visit_submit'),
    path('reports/<int:pk>/approve/', views.field_visit_approve, name='field_visit_approve'),
    path('reports/<int:pk>/reject/', views.field_visit_reject, name='field_visit_reject'),
    
    # Export
    path('reports/<int:pk>/export/word/', views.field_visit_export_word, name='field_visit_export_word'),
]
