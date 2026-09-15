from django.urls import path

from . import views

app_name = 'icpd'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('report/', views.report_entry, name='report_entry'),
	path('report/actuals/', views.actual_report_list, name='actual_report_list'),
	path('report/actuals/<int:pk>/', views.actual_report_detail, name='actual_report_detail'),
    path('report/actuals/<int:pk>/export/<str:export_format>/', views.actual_report_export, name='actual_report_export'),
	path('report/narratives/', views.narrative_report_list, name='narrative_report_list'),
    path('report/narratives/<int:pk>/', views.narrative_report_detail, name='narrative_report_detail'),
    path('report/narratives/<int:pk>/export/<str:export_format>/', views.narrative_detail_export, name='narrative_detail_export'),
    path('report/review/', views.submission_review, name='submission_review'),
    path('report/submissions/actual/<int:pk>/review/', views.actual_submission_review, name='actual_submission_review'),
    path('report/submissions/expenditure/<int:pk>/review/', views.expenditure_submission_review, name='expenditure_submission_review'),
    path('report/submissions/narrative/<int:pk>/review/', views.narrative_submission_review, name='narrative_submission_review'),
    path('report/narrative/export/', views.narrative_report_export, name='narrative_report_export'),
    path('access/', views.commitment_access, name='commitment_access'),
    path('commitments/<int:pk>/', views.commitment_detail, name='commitment_detail'),
    path('commitments/add/', views.commitment_create, name='commitment_create'),
    path('commitments/<int:pk>/edit/', views.commitment_update, name='commitment_update'),
    path('commitments/<int:pk>/delete/', views.commitment_delete, name='commitment_delete'),
    path('objectives/add/', views.objective_create, name='objective_create'),
    path('objectives/<int:pk>/edit/', views.objective_update, name='objective_update'),
    path('objectives/<int:pk>/delete/', views.objective_delete, name='objective_delete'),
    path('activities/add/', views.activity_create, name='activity_create'),
    path('activities/<int:pk>/edit/', views.activity_update, name='activity_update'),
    path('activities/<int:pk>/delete/', views.activity_delete, name='activity_delete'),
    path('activity-indicators/', views.activity_indicator_list, name='activity_indicator_list'),
    path('activity-indicators/add/', views.activity_indicator_create, name='activity_indicator_create'),
    path('activity-indicators/<int:pk>/edit/', views.activity_indicator_update, name='activity_indicator_update'),
    path('activity-indicators/<int:pk>/delete/', views.activity_indicator_delete, name='activity_indicator_delete'),
    path('year-data/add/', views.indicator_year_data_create, name='indicator_year_data_create'),
    path('year-data/<int:pk>/edit/', views.indicator_year_data_update, name='indicator_year_data_update'),
    path('year-data/<int:pk>/delete/', views.indicator_year_data_delete, name='indicator_year_data_delete'),
    path('activity-expenditure/add/', views.activity_year_data_create, name='activity_year_data_create'),
    path('activity-expenditure/<int:pk>/edit/', views.activity_year_data_update, name='activity_year_data_update'),
]