"""
Forms for Field Monitoring Visit Report
"""

from django import forms
from django.forms import inlineformset_factory
from .models import (
    FieldVisitReport,
    VisitingTeamMember,
    PersonMet,
    ServiceProvided,
    Challenge,
    BestPractice,
    CollaboratingPartner,
    FieldVisitAttachment,
)


class FieldVisitReportForm(forms.ModelForm):
    """Main field visit report form"""
    
    class Meta:
        model = FieldVisitReport
        fields = [
            'organization_name',
            'county',
            'location_details',
            'visit_date',
            'last_visit_date',
            'report_date',
            'data_collection_methods',
        ]
        widgets = {
            'organization_name': forms.TextInput(attrs={'class': 'form-control'}),
            'county': forms.Select(attrs={'class': 'form-control'}),
            'location_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'visit_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'last_visit_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'report_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_collection_methods': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class VisitingTeamMemberForm(forms.ModelForm):
    """Form for visiting team members"""
    
    class Meta:
        model = VisitingTeamMember
        fields = ['name', 'title_organization', 'telephone', 'email']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'title_organization': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


class PersonMetForm(forms.ModelForm):
    """Form for persons met during visit"""
    
    class Meta:
        model = PersonMet
        fields = ['name', 'title']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ServiceProvidedForm(forms.ModelForm):
    """Form for services/activities with findings"""
    
    class Meta:
        model = ServiceProvided
        fields = ['service_name', 'indicator', 'findings', 'recommended_action']
        widgets = {
            'service_name': forms.TextInput(attrs={'class': 'form-control'}),
            'indicator': forms.Select(attrs={'class': 'form-control'}),
            'findings': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'recommended_action': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class ChallengeForm(forms.ModelForm):
    """Form for challenges and issues"""
    
    class Meta:
        model = Challenge
        fields = ['challenge_description', 'recommendation', 'priority']
        widgets = {
            'challenge_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'recommendation': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
        }


class BestPracticeForm(forms.ModelForm):
    """Form for best practices"""
    
    class Meta:
        model = BestPractice
        fields = ['practice_description', 'lessons_learned', 'replicable']
        widgets = {
            'practice_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'lessons_learned': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'replicable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CollaboratingPartnerForm(forms.ModelForm):
    """Form for collaborating partners"""
    
    class Meta:
        model = CollaboratingPartner
        fields = ['partner', 'partner_name', 'partnership_nature', 'contact_person', 'contact_details']
        widgets = {
            'partner': forms.Select(attrs={'class': 'form-select'}),
            'partner_name': forms.TextInput(attrs={'class': 'form-control'}),
            'partnership_nature': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_details': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from partners.models import Partner
        self.fields['partner'].queryset = Partner.objects.filter(status='active')
        self.fields['partner'].empty_label = 'Select a registered partner (optional)'
        self.fields['partner_name'].help_text = 'Use this only when the partner is not in the registered partner list.'

    def clean(self):
        cleaned_data = super().clean()
        partner = cleaned_data.get('partner')
        partner_name = cleaned_data.get('partner_name', '').strip()
        if partner:
            cleaned_data['partner_name'] = partner.name
        elif not partner_name:
            self.add_error('partner_name', 'Select a registered partner or enter an unlisted partner name.')
        return cleaned_data


class FieldVisitAttachmentForm(forms.ModelForm):
    """Form for attachments"""
    
    class Meta:
        model = FieldVisitAttachment
        fields = ['document_type', 'file', 'description']
        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


# Inline formsets for related models
VisitingTeamMemberFormSet = inlineformset_factory(
    FieldVisitReport,
    VisitingTeamMember,
    form=VisitingTeamMemberForm,
    extra=1,
    can_delete=True,
)

PersonMetFormSet = inlineformset_factory(
    FieldVisitReport,
    PersonMet,
    form=PersonMetForm,
    extra=1,
    can_delete=True,
)

ServiceProvidedFormSet = inlineformset_factory(
    FieldVisitReport,
    ServiceProvided,
    form=ServiceProvidedForm,
    extra=1,
    can_delete=True,
)

ChallengeFormSet = inlineformset_factory(
    FieldVisitReport,
    Challenge,
    form=ChallengeForm,
    extra=1,
    can_delete=True,
)

BestPracticeFormSet = inlineformset_factory(
    FieldVisitReport,
    BestPractice,
    form=BestPracticeForm,
    extra=1,
    can_delete=True,
)

CollaboratingPartnerFormSet = inlineformset_factory(
    FieldVisitReport,
    CollaboratingPartner,
    form=CollaboratingPartnerForm,
    extra=1,
    can_delete=True,
)

FieldVisitAttachmentFormSet = inlineformset_factory(
    FieldVisitReport,
    FieldVisitAttachment,
    form=FieldVisitAttachmentForm,
    extra=1,
    can_delete=True,
)