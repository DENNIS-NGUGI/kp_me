from django.urls import path
from . import views

app_name = 'indicators'

urlpatterns = [
    path('', views.indicator_list, name='list'),
    path('add/', views.indicator_add, name='add'),
    path('<str:code>/edit/', views.indicator_edit, name='edit'),
    path('<str:code>/delete/', views.indicator_delete, name='delete'),
    path('thematic-areas/', views.thematic_area_list, name='thematic_areas'),
]
