from django.contrib import admin

from .models import Activity, ActivityIndicator, ActivityYearData, Commitment, IndicatorYearData, Objective


class ObjectiveInline(admin.TabularInline):
	model = Objective
	extra = 0


@admin.register(Commitment)
class CommitmentAdmin(admin.ModelAdmin):
	list_display = ('title', 'is_active', 'sort_order')
	list_filter = ('is_active',)
	search_fields = ('title', 'description')
	ordering = ('sort_order', 'title')
	inlines = (ObjectiveInline,)


@admin.register(Objective)
class ObjectiveAdmin(admin.ModelAdmin):
	list_display = ('title', 'commitment', 'sort_order')
	list_filter = ('commitment',)
	search_fields = ('title', 'description')
	ordering = ('commitment', 'sort_order', 'title')


class ActivityIndicatorInline(admin.TabularInline):
	model = ActivityIndicator
	extra = 0


class ActivityYearDataInline(admin.TabularInline):
	model = ActivityYearData
	extra = 0


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
	list_display = ('title', 'objective', 'timeline', 'responsibility', 'budget_amount')
	list_filter = ('objective__commitment',)
	search_fields = ('title', 'responsibility')
	ordering = ('objective', 'sort_order', 'id')
	inlines = (ActivityIndicatorInline, ActivityYearDataInline)


class IndicatorYearDataInline(admin.TabularInline):
	model = IndicatorYearData
	extra = 0


@admin.register(ActivityIndicator)
class ActivityIndicatorAdmin(admin.ModelAdmin):
	list_display = ('code', 'name', 'activity', 'baseline_value', 'baseline_year')
	list_filter = ('activity__objective__commitment',)
	search_fields = ('code', 'name', 'activity__title')
	autocomplete_fields = ('activity',)
	readonly_fields = ('code',)
	inlines = (IndicatorYearDataInline,)


@admin.register(IndicatorYearData)
class IndicatorYearDataAdmin(admin.ModelAdmin):
	list_display = ('activity_indicator', 'financial_year', 'target_value', 'achievement_value', 'status')
	list_filter = ('financial_year', 'status')
	search_fields = ('activity_indicator__code', 'activity_indicator__name')
	autocomplete_fields = ('activity_indicator',)


@admin.register(ActivityYearData)
class ActivityYearDataAdmin(admin.ModelAdmin):
	list_display = ('activity', 'financial_year', 'expenditure_amount')
	list_filter = ('financial_year', 'activity__objective__commitment')
	search_fields = ('activity__title',)
	autocomplete_fields = ('activity',)
