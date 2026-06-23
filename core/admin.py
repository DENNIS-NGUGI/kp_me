from django.contrib import admin
from .models import County, SubCounty, Quarter

@admin.register(County)
class CountyAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'region', 'is_active']
    list_filter = ['region', 'is_active']
    search_fields = ['name', 'code']
    ordering = ['name']

@admin.register(SubCounty)
class SubCountyAdmin(admin.ModelAdmin):
    list_display = ['name', 'county', 'code', 'is_active']
    list_filter = ['county', 'is_active']
    search_fields = ['name', 'code']

@admin.register(Quarter)
class QuarterAdmin(admin.ModelAdmin):
    list_display = ['name', 'fiscal_year', 'quarter_number', 'start_date', 'submission_deadline', 'is_active', 'is_closed']
    list_filter = ['fiscal_year', 'is_active', 'is_closed']
    search_fields = ['name', 'fiscal_year']
    ordering = ['-start_date']
