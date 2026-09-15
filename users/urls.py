from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('terms/', views.terms_conditions, name='terms'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('captcha-refresh/', views.ajax_captcha_refresh, name='captcha_refresh'),
    path('password-reset/', views.UserPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.password_reset_done, name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', views.UserPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    
    # Profile
    path('pending-verification/', views.pending_verification, name='pending_verification'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('password-change/', views.change_password, name='change_password'),
    path('permission-denied/', views.permission_denied, name='permission_denied'),
    
    # User Management
    path('organizations/', views.organization_management, name='organization_management'),
    path('users/', views.user_management, name='user_management'),
    path('users/add/', views.user_add, name='user_add'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:pk>/toggle-status/', views.user_toggle_status, name='user_toggle_status'),
    path('users/<int:pk>/delete/', views.user_delete, name='user_delete'),
    
    # Role Management
    path('roles/', views.role_list, name='role_list'),
    path('roles/add/', views.role_add, name='role_add'),
    path('roles/<int:pk>/edit/', views.role_edit, name='role_edit'),
    path('roles/<int:pk>/delete/', views.role_delete, name='role_delete'),
    path('roles/<int:pk>/permissions/', views.role_update_permissions, name='role_update_permissions'),
    path('roles/<int:pk>/clone/', views.role_clone, name='role_clone'),
]