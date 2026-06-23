from django.urls import path
from . import views

app_name = 'partners'

urlpatterns = [
    # Partner URLs
    path('', views.partner_list, name='list'),
    path('add/', views.partner_add, name='add'),
    path('<int:pk>/', views.partner_detail, name='detail'),
    path('<int:pk>/edit/', views.partner_edit, name='edit'),
    
    # Project URLs
    path('projects/', views.project_list, name='project_list'),
    path('projects/add/', views.project_add, name='project_add'),
    path('projects/<int:pk>/', views.project_detail, name='project_detail'),
    path('projects/<int:pk>/edit/', views.project_edit, name='project_edit'),
    
    # Milestone URLs
    path('projects/<int:project_pk>/milestone/add/', views.project_milestone_add, name='milestone_add'),
    path('milestone/<int:pk>/complete/', views.project_milestone_complete, name='milestone_complete'),
    
    # Dashboard
    path('dashboard/', views.project_dashboard, name='dashboard'),
]
