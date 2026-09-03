from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/county-boundaries/', views.county_map_boundaries, name='county_map_boundaries'),
    path('report/', views.report_list, name='report_list'),
    path('report/access/', views.report_access, name='report_access'),
    path('report/<str:report_key>/', views.report_preview, name='preview'),
    path('report/<str:report_key>/export/<str:export_format>/', views.report_export, name='export'),
]