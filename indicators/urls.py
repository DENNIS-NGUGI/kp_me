from django.urls import path
from . import views

app_name = 'indicators'

urlpatterns = [
    # List view
    path('', views.indicator_list, name='list'),
    
    # Add indicator
    path('add/', views.indicator_add, name='add'),
    
    # API endpoint for AJAX (moved to a separate path)
    path('api/<str:code>/detail/', views.indicator_detail_api, name='detail_api'),
    
    # Regular detail view (if you need a full page)
    path('<str:code>/', views.indicator_detail, name='detail'),
    
    # Edit and delete
    path('<str:code>/edit/', views.indicator_edit, name='edit'),
    path('<str:code>/delete/', views.indicator_delete, name='delete'),
    
    # Thematic Areas
    path('thematic-areas/', views.thematic_area_list, name='thematic_areas'),
    path('thematic-areas/add/', views.thematic_area_add, name='thematic_area_add'),
    path('thematic-areas/<int:pk>/edit/', views.thematic_area_edit, name='thematic_area_edit'),
    path('thematic-areas/<int:pk>/delete/', views.thematic_area_delete, name='thematic_area_delete'),
]