# Field Monitoring Visit Report Module

## Overview
The Field Monitoring Visit Report module automates the NCPD Regional Offices M&E field visit reporting template. It allows users to systematically capture, manage, and export field monitoring data through a structured digital system.

---

## ✅ What Was Created

### 1. **Django App: `field_monitoring`**
A new dedicated app for managing field visit reports and related data.

### 2. **Database Models**

#### Core Model: `FieldVisitReport`
The main report container capturing:
- **Report Info**: Auto-generated code (FMR-YYYY-XXX), status, report date
- **Visit Details**: Organization name, county, location, visit date, previous visit date
- **Personnel**: Who compiled/submitted/approved the report
- **Data Collection Methods**: How data was collected
- **Audit Trail**: Creation/update timestamps and approvals

**Status Workflow**: Draft → Submitted → Reviewed → Approved → Archived

#### Related Models (One-to-Many):

1. **VisitingTeamMember**
   - Name, Title/Organization, Telephone, Email
   - Multiple team members per visit

2. **PersonMet**
   - Name, Title/Position
   - Key stakeholders met during visit

3. **ServiceProvided**
   - Service name, Related indicator (optional)
   - Findings observed
   - Recommended actions
   - Multiple services per visit

4. **Challenge**
   - Challenge description
   - Recommendation/solution
   - Priority level (Low/Medium/High/Critical)
   - Multiple challenges per visit

5. **BestPractice**
   - Practice description
   - Lessons learned
   - Is it replicable? (Yes/No)
   - Multiple practices per visit

6. **CollaboratingPartner**
   - Partner name, partnership nature
   - Contact person, contact details
   - Multiple partners per visit

7. **FieldVisitAttachment**
   - Document type (Photo, Document, Video, Data)
   - File upload
   - Description
   - Multiple attachments per visit

---

## 📊 Database Schema

```
FieldVisitReport (Main)
├── VisitingTeamMember (1:M)
├── PersonMet (1:M)
├── ServiceProvided (1:M)
│   └── Related to Indicator
├── Challenge (1:M)
├── BestPractice (1:M)
├── CollaboratingPartner (1:M)
└── FieldVisitAttachment (1:M)

Foreign Keys:
- ForeignKey(County) on field_monitoring_fieldvisitreport
- ForeignKey(User) x4 on field_monitoring_fieldvisitreport
- ForeignKey(Indicator, optional) on field_monitoring_serviceprovided
- ForeignKey(FieldVisitReport) on all related models
```

---

## 🎯 Key Features

### 1. **Auto-Generated Report Codes**
- Format: `FMR-2025-001`, `FMR-2025-002`, etc.
- Automatically generated on save based on year and sequence

### 2. **Status Tracking**
- Draft, Submitted, Reviewed, Approved, Archived
- Bulk actions for status changes (via admin)

### 3. **Comprehensive Data Capture**
All template sections are now digital:
- ✅ Report metadata
- ✅ Visiting team information
- ✅ Stakeholders met
- ✅ Services & findings
- ✅ Challenges & recommendations
- ✅ Best practices
- ✅ Collaborating partners
- ✅ Supporting documents

### 4. **Django Admin Integration**
- Full CRUD operations via Django admin
- Inline editing of related data
- Bulk actions for approval workflows
- Color-coded status indicators
- Priority level badges for challenges
- File management for attachments

### 5. **Validation**
- Report date must be after visit date
- Previous visit date must be before current visit date
- All required fields enforced
- Custom validation in model.clean()

### 6. **Audit Trail**
- Created_at, updated_at timestamps
- Tracking of who compiled, submitted, and approved
- Approval timestamp recording

---

## 🚀 How to Use

### Access via Django Admin
```
URL: http://kppimes.ncpd.go.ke/admin/field_monitoring/
Username/Password: Your admin credentials
```

### Create a New Field Visit Report

1. **Go to Django Admin** → Field Monitoring → Field Visit Reports
2. **Click "Add Field Visit Report"**
3. **Fill in Report Details**:
   - Organization name
   - County
   - Location details
   - Visit date, previous visit date
   - Report date
   - Data collection methods

4. **Add Team Members** (inline form)
   - Click "Add another Visiting Team Member"
   - Enter: Name, Title/Organization, Telephone, Email

5. **Add Persons Met** (inline form)
   - Click "Add another Person Met"
   - Enter: Name, Title

6. **Add Services Provided**
   - Click "Add another Service Provided"
   - Enter: Service name, indicator (optional), findings, recommended actions

7. **Add Challenges**
   - Click "Add another Challenge"
   - Enter: Challenge description, recommendation, priority

8. **Add Best Practices**
   - Click "Add another Best Practice"
   - Enter: Practice description, lessons learned, replicable? (checkbox)

9. **Add Partners**
   - Click "Add another Collaborating Partner"
   - Enter: Partner name, partnership nature, contact person, contact details

10. **Add Attachments**
    - Click "Add another Field Visit Attachment"
    - Choose document type, upload file, add description

11. **Save** and set status to "Submitted"

### Export Reports

Currently supported via Django admin:
- View as HTML
- Print to PDF (using browser print)
- Download raw data (using Django admin export features)

**Future Enhancement**: Export to Word template format (Phase 2)

---

## 📋 Forms Available

Location: `field_monitoring/forms.py`

```python
FieldVisitReportForm  # Main report form
VisitingTeamMemberForm
PersonMetForm
ServiceProvidedForm
ChallengeForm
BestPracticeForm
CollaboratingPartnerForm
FieldVisitAttachmentForm

# Inline formsets (multiple items)
VisitingTeamMemberFormSet
PersonMetFormSet
ServiceProvidedFormSet
ChallengeFormSet
BestPracticeFormSet
CollaboratingPartnerFormSet
FieldVisitAttachmentFormSet
```

---

## 🔐 Permissions

Custom permissions available:
```python
'can_approve_field_visit'  # Can approve field visit reports
'can_export_field_visit'   # Can export field visit reports
```

Standard Django permissions also apply:
- `view_fieldvisitreport`
- `add_fieldvisitreport`
- `change_fieldvisitreport`
- `delete_fieldvisitreport`

---

## 📊 Querying Data (for developers)

```python
from field_monitoring.models import FieldVisitReport, Challenge

# Get all approved reports
approved_reports = FieldVisitReport.objects.filter(status='approved')

# Get critical challenges
critical_challenges = Challenge.objects.filter(
    priority='critical',
    visit__status='approved'
)

# Get best practices by county
from core.models import County
county = County.objects.get(name='Nairobi')
practices = BestPractice.objects.filter(
    visit__county=county,
    replicable=True
)

# Export data for analysis
reports = FieldVisitReport.objects.filter(
    visit_date__year=2025
).select_related(
    'county',
    'report_compiled_by'
).prefetch_related(
    'services_provided',
    'challenges',
    'best_practices',
    'collaborating_partners'
)
```

---

## 🔧 Next Steps (Phase 2 - Recommended)

### 1. **Word Template Export**
```python
# field_monitoring/exports.py
def export_to_word(report_id):
    """Generate Word document from report"""
    from python_docx import Document
    # Map model data to template
    # Generate .docx file
    # Return for download
```

### 2. **PDF Export**
```python
def export_to_pdf(report_id):
    """Generate PDF from report"""
    from reportlab.lib.pagesizes import A4
    # Create formatted PDF
    # Return for download
```

### 3. **Front-end Views & Forms**
```
field_monitoring/
├── views.py  (CRUD views for reports)
├── urls.py   (URL routing)
├── templates/
│   ├── list.html (List all reports)
│   ├── detail.html (View single report)
│   ├── form.html (Create/Edit report)
│   └── print.html (Print-friendly version)
```

### 4. **Notifications & Alerts**
- Auto-notify supervisors when new reports submitted
- Escalation for overdue submissions
- Approval reminders

### 5. **Analytics Dashboard**
- Report submission statistics
- Challenge tracking dashboard
- Best practices library
- Partner collaboration network

### 6. **Mobile-Friendly Version**
- Mobile forms for field data entry
- Offline sync capability
- Photo upload from mobile camera

---

## 📦 Installation Checklist

✅ **Already Done:**
- App created: `field_monitoring`
- Models: 8 models created
- Admin: Full admin interface configured
- Forms: All forms and formsets created
- Migrations: Applied to database

**What You Need to Do:**

1. Update permissions in roles:
   ```bash
   python manage.py shell
   >>> from django.contrib.auth.models import Permission
   >>> from field_monitoring.models import FieldVisitReport
   >>> # Permissions auto-created by Django
   ```

2. Train users on data entry process

3. Create export features (Phase 2)

4. Integrate with dashboard/reports module

---

## 🎨 Admin Interface Features

### FieldVisitReport Admin
- Color-coded status badges
- Inline editing of all related data
- Bulk actions:
  - Mark as Submitted
  - Mark as Reviewed
  - Approve (with timestamp and approver tracking)
- Advanced search
- Filtering by county, date, status

### Challenge Admin
- Priority level badges (color-coded)
- Quick filtering by priority
- Search across descriptions and recommendations

### BestPractice Admin
- Replicability indicator
- Easy identification of replicable practices
- Lessons learned tracking

---

## 📝 Field Mapping from Template

Template Section → Model/Field Mapping:

```
HEADER
├── Report Compiled by → FieldVisitReport.report_compiled_by
├── Submitted on → FieldVisitReport.report_date
└── [auto-generated code] → FieldVisitReport.report_code

REPORT DETAILS
├── Name of Organization → FieldVisitReport.organization_name
├── Report by → FieldVisitReport.report_submitted_by
├── Date of report → FieldVisitReport.report_date
├── Location → FieldVisitReport.location_details
├── Date of last visit → FieldVisitReport.last_visit_date
├── Date of visit → FieldVisitReport.visit_date
└── County → FieldVisitReport.county

MEMBERS OF VISITING TEAM (table rows)
└── VisitingTeamMember (name, title, phone, email)

PERSONS MET (table rows)
└── PersonMet (name, title)

DATA COLLECTION USED
└── FieldVisitReport.data_collection_methods

A. SERVICES PROVIDED
└── ServiceProvided (service_name, findings, recommended_action)

CHALLENGES & RECOMMENDATIONS
└── Challenge (challenge_description, recommendation, priority)

BEST PRACTICE
└── BestPractice (practice_description, lessons_learned, replicable)

COLLABORATING PARTNERS
└── CollaboratingPartner (partner_name, contact_person, contact_details)

SUPPORTING DOCUMENTS
└── FieldVisitAttachment (document_type, file, description)
```

---

## 🐛 Troubleshooting

**Issue**: Can't see field_monitoring in admin
**Solution**: 
```bash
python manage.py migrate
python manage.py collectstatic
# Restart server
```

**Issue**: Missing permissions
**Solution**:
```bash
python manage.py migrate contenttypes
python manage.py migrate auth
python manage.py migrate field_monitoring
```

**Issue**: File upload not working
**Solution**: Ensure `MEDIA_ROOT` and `MEDIA_URL` configured in settings.py ✓ Already done

---

## 📞 Support & Documentation

For detailed Django model documentation:
```bash
python manage.py shell
>>> from field_monitoring.models import FieldVisitReport
>>> help(FieldVisitReport)
```

For form documentation:
```bash
python manage.py shell
>>> from field_monitoring.forms import FieldVisitReportForm
>>> help(FieldVisitReportForm)
```

---

**Status**: ✅ **Production Ready**
**Created**: 2026-08-31
**App Location**: `/home/dngugi/projects/kp_me/field_monitoring/`
**Models Count**: 8
**Admin Pages**: 8
**Forms**: 7 + 7 formsets

