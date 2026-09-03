from django import forms

from .models import Activity, ActivityIndicator, ActivityYearData, Commitment, CommitmentNarrativeReport, IndicatorYearData, Objective


class ActivityChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, activity):
        return f'{activity.objective.commitment.title} | {activity.objective.title} | {activity.title}'


class BootstrapModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'


class CommitmentForm(BootstrapModelForm):
    class Meta:
        model = Commitment
        fields = ('title', 'description', 'sort_order', 'is_active')
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}


class ObjectiveForm(BootstrapModelForm):
    class Meta:
        model = Objective
        fields = ('commitment', 'title', 'description', 'sort_order')
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}


class ActivityForm(BootstrapModelForm):
    class Meta:
        model = Activity
        fields = (
            'objective', 'title', 'timeline', 'responsibility', 'budget_amount',
            'budget_currency', 'remarks', 'sort_order',
        )
        widgets = {
            'title': forms.Textarea(attrs={'rows': 3}),
            'remarks': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {'budget_amount': 'Budget (KES millions)'}


class ActivityIndicatorForm(BootstrapModelForm):
    class Meta:
        model = ActivityIndicator
        fields = ('activity', 'name', 'baseline_value', 'baseline_year', 'notes')
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['activity'] = ActivityChoiceField(
            queryset=Activity.objects.select_related('objective__commitment'),
            widget=forms.Select(attrs={'class': 'form-select'}),
        )


class IndicatorYearDataForm(BootstrapModelForm):
    class Meta:
        model = IndicatorYearData
        fields = ('activity_indicator', 'financial_year', 'target_value')


class IndicatorYearActualsForm(BootstrapModelForm):
    class Meta:
        model = IndicatorYearData
        fields = ('achievement_value', 'status', 'remarks')
        widgets = {'remarks': forms.Textarea(attrs={'rows': 3})}


class ActivityYearDataForm(BootstrapModelForm):
    class Meta:
        model = ActivityYearData
        fields = ('activity', 'financial_year', 'expenditure_amount', 'remarks')
        widgets = {'remarks': forms.Textarea(attrs={'rows': 3})}
        labels = {'expenditure_amount': 'Actual Expenditure (KES millions)'}


class ActivityYearActualsForm(BootstrapModelForm):
    class Meta:
        model = ActivityYearData
        fields = ('expenditure_amount', 'remarks')
        widgets = {'remarks': forms.Textarea(attrs={'rows': 3})}
        labels = {'expenditure_amount': 'Actual Expenditure (KES millions)'}


class CommitmentNarrativeReportForm(BootstrapModelForm):
    class Meta:
        model = CommitmentNarrativeReport
        fields = (
            'introduction',
            'executive_summary',
            'abbreviations',
            'other_actor_contributions',
            'facilitating_factors',
            'challenges',
            'opportunities',
            'conclusion_and_recommendations',
            'references',
        )
        labels = {
            'introduction': 'a. Introduction (1-2 paragraphs)',
            'executive_summary': 'b. Executive summary',
            'abbreviations': 'c. Abbreviations',
            'other_actor_contributions': 'e. Contribution by other actors',
            'facilitating_factors': 'f. Facilitating factors',
            'challenges': 'What challenges slowed progress?',
            'opportunities': 'What opportunities to enhance implementation exist?',
            'conclusion_and_recommendations': 'g. Conclusion and Recommendations',
            'references': 'h. References',
        }
        widgets = {
            'introduction': forms.Textarea(attrs={'rows': 6, 'placeholder': 'Brief background of the commitment.'}),
            'abbreviations': forms.Textarea(attrs={'rows': 4}),
            'executive_summary': forms.Textarea(attrs={'rows': 5}),
            'other_actor_contributions': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Note contributions from CSOs, development partners, counties, private sector etc.'}),
            'facilitating_factors': forms.Textarea(attrs={'rows': 4, 'placeholder': 'What enabled progress?'}),
            'challenges': forms.Textarea(attrs={'rows': 4}),
            'opportunities': forms.Textarea(attrs={'rows': 4}),
            'conclusion_and_recommendations': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Brief takeaways and priority next steps.'}),
            'references': forms.Textarea(attrs={'rows': 5}),
        }