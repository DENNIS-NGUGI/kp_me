from django.contrib import admin
from .models import ThematicArea, Indicator

@admin.register(ThematicArea)
class ThematicAreaAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'sort_order']
    search_fields = ['name', 'code']
    ordering = ['sort_order']

@admin.register(Indicator)
class IndicatorAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'thematic_area', 'indicator_type', 'data_type', 
                    'target_value', 'unit', 'min_value', 'max_value', 'frequency', 'is_active']
    list_filter = ['thematic_area', 'indicator_type', 'data_type', 'frequency', 'is_active']
    search_fields = ['code', 'name']
    ordering = ['thematic_area', 'code']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'thematic_area', 'indicator_type', 'description')
        }),
        ('Measurement', {
            'fields': ('data_type', 'unit', 'formula')
        }),
        ('Target & Source', {
            'fields': ('target_value', 'source_system', 'frequency')
        }),
        ('Range Validation', {
            'fields': ('min_value', 'max_value'),
            'classes': ('collapse',),
            'description': 'Set minimum and maximum allowed values for this indicator. Leave blank for no limit.'
        }),
        ('Disaggregation', {
            'fields': ('disaggregation_by_age', 'disaggregation_by_sex', 'disaggregation_by_region', 'disaggregation_note')
        }),
        ('Status', {
            'fields': ('is_active', 'is_custom', 'notes')
        }),
    )
    
    # Add help text for min/max
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        return fieldsets