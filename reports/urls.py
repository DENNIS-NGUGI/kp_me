from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard_view'),
    path('reports/', views.report_list, name='report_list'),
    path('reports/generate/', views.generate_report, name='generate_report'),
    path('reports/quarterly/', views.quarterly_report, name='quarterly_report'),
    path('reports/annual/', views.annual_report, name='annual_report'),
    path('reports/thematic/<str:code>/', views.thematic_report, name='thematic_report'),
    path('reports/sdg/', views.sdg_report, name='sdg_report'),
    path('reports/pending/', views.pending_reports, name='pending_reports'),
    path('reports/export/<str:format>/', views.export_report, name='export_report'),
    
    # New Export/Import URLs
    path('reports/export/', views.export_data, name='export_data'),
    path('reports/export/excel/', views.export_excel, name='export_excel'),
    path('reports/export/indicators/', views.export_indicators, name='export_indicators'),
    path('reports/import/', views.import_indicators, name='import_indicators'),
    path('reports/template/<str:template_type>/', views.download_template, name='download_template'),
]