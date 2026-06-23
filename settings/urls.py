from django.urls import path
from . import views

app_name = 'settings'

urlpatterns = [
    # System Settings
    path('', views.settings_index, name='index'),
    path('add/', views.settings_add, name='add'),
    path('edit/<str:key>/', views.settings_edit, name='edit'),
    path('delete/<str:key>/', views.settings_delete, name='delete'),
    
    # Audit Log
    path('audit-log/', views.audit_log, name='audit_log'),
    
    # Quarter Management
    path('quarters/', views.quarter_management, name='quarters'),
    path('quarters/add/', views.quarter_add, name='quarter_add'),
    path('quarters/edit/<int:pk>/', views.quarter_edit, name='quarter_edit'),
    path('quarters/toggle/<int:pk>/', views.quarter_toggle, name='quarter_toggle'),
    path('quarters/delete/<int:pk>/', views.quarter_delete, name='quarter_delete'),

    # County Management
    path('counties/', views.county_management, name='counties'),
    path('counties/add/', views.county_add, name='county_add'),
    path('counties/edit/<int:pk>/', views.county_edit, name='county_edit'),
    path('counties/toggle/<int:pk>/', views.county_toggle, name='county_toggle'),
    path('counties/delete/<int:pk>/', views.county_delete, name='county_delete'),
    path('counties/export/', views.county_export, name='county_export'),
    path('counties/import/', views.county_import, name='county_import'),
]


