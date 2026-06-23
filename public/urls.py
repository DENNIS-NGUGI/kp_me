from django.urls import path
from . import views

app_name = 'public'

urlpatterns = [
    path('', views.landing, name='landing'),
    path('api/stats/', views.stats_api, name='stats_api'),
]
