from django.urls import path
from . import views

app_name = 'data_entry'

urlpatterns = [
    path('', views.data_entry_list, name='list'),
    path('entry/', views.data_entry_form, name='entry'),
    path('entry/<int:pk>/', views.data_entry_detail, name='detail'),
    path('entry/<int:pk>/edit/', views.data_entry_edit, name='edit'),
    path('entry/<int:pk>/submit/', views.data_entry_submit, name='submit'),
    path('entry/<int:pk>/approve/', views.data_entry_approve, name='approve'),
    path('entry/<int:pk>/reject/', views.data_entry_reject, name='reject'),
    path('entry/<int:pk>/delete/', views.data_entry_delete, name='delete'),
    path('pending/', views.pending_approvals, name='pending'),
    
]
