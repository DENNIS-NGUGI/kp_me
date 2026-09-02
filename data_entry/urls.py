# data_entry/urls.py - COMPLETE FIXED VERSION

from django.urls import path
from . import views

app_name = 'data_entry'

urlpatterns = [
    # ===== MAIN VIEWS =====
    path('', views.data_entry_list, name='list'),
    path('form/', views.data_entry_form, name='form'),
    
    # ===== API ENDPOINTS (MUST COME BEFORE ANY <int:pk> PATTERNS) =====
    path('api/<int:pk>/detail/', views.data_entry_detail_api, name='api_detail'),
    
    # ===== SINGLE ENTRY OPERATIONS (WITH PK) =====
    path('<int:pk>/', views.data_entry_detail, name='detail'),
    path('<int:pk>/edit/', views.data_entry_edit, name='edit'),
    path('<int:pk>/submit/', views.data_entry_submit, name='submit'),
    path('<int:pk>/delete/', views.data_entry_delete, name='delete'),
    
    # ===== APPROVAL OPERATIONS =====
    path('<int:pk>/approve/', views.data_entry_approve, name='approve'),
    path('<int:pk>/reject/', views.data_entry_reject, name='reject'),
    
    # ===== PENDING APPROVALS =====
    path('pending/', views.pending_approvals, name='pending'),
    
    # ===== BULK OPERATIONS =====
    path('bulk-submit/', views.data_entry_submit_bulk, name='bulk_submit'),
]