from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'users'

urlpatterns = [
    # Auth Management
    path('login/', views.login_view, name='login'),  # <-- USE YOUR CUSTOM VIEW
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    
    # Role Management
    path('roles/', views.role_list, name='role_list'),
    path('roles/add/', views.role_add, name='role_add'),
    path('roles/<int:pk>/edit/', views.role_edit, name='role_edit'),
    path('roles/<int:pk>/delete/', views.role_delete, name='role_delete'),
    path('roles/<int:pk>/permissions/', views.role_update_permissions, name='role_update_permissions'),

    # User Management
    path('manage/', views.user_management, name='user_management'),
    path('manage/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('manage/<int:pk>/toggle/', views.user_toggle_status, name='user_toggle'),
    path('manage/<int:pk>/delete/', views.user_delete, name='user_delete'),
]