# Educational Platform SaaS — Django REST Framework Backend Blueprint

## 1. Role and Objective

Act as a **principal backend architect and senior Django REST Framework engineer**. Build a production-ready, secure, modular, multi-tenant Educational Platform SaaS backend.

The platform must support:

- Schools
- Colleges
- Universities
- Professional institutes
- Coaching centers
- Online tuition and learning providers

Treat every institution as a **tenant/organization**. Do not design this as a school-only CRUD application.

The backend must be maintainable by another engineering team. Use clear domain boundaries, explicit business rules, strong tenant isolation, automated tests, API documentation, audit logging, and deployment documentation.

Do not blindly implement every future feature in the first release. Build the foundation and core modules first, then add advanced modules incrementally.

---

## 2. Mandatory Technology Stack

Use:

- Python 3.12+
- Django
- Django REST Framework
- PostgreSQL
- Redis
- Celery for background jobs
- JWT authentication with secure HTTP-only cookie strategy where appropriate
- `django-filter`
- OpenAPI documentation using `drf-spectacular`
- `pytest`, `pytest-django`, and factory-based test data
- Ruff or Black + isort for formatting/linting
- pre-commit hooks
- Docker and Docker Compose for local development
- Object storage such as S3-compatible storage for uploaded documents
- Sentry or an equivalent error-tracking service
- Structured application logging
- Environment variables for all secrets and environment-specific configuration

Use a **modular monolith first**. Do not split into microservices unless a documented scaling or ownership requirement justifies it.

---

## 3. Architecture Principles

Use clear layers:

1. Presentation/API layer
2. Authentication and authorization layer
3. Application/service layer
4. Domain/business-rule layer
5. Data/model/repository layer
6. Integration/provider layer
7. Background task layer

Critical business rules must live on the backend. Never trust client-provided values for:

- tenant ID
- role
- permissions
- payment status
- marks
- prices
- discounts
- ownership
- approval status
- published status

Use:

- UUID primary keys
- timestamps
- created_by and updated_by where relevant
- soft deletion or archival where appropriate
- database constraints
- unique constraints
- check constraints
- indexes
- transactions
- optimistic or safe update strategies
- explicit state transitions

---

## 4. Multi-Tenant Architecture

### Tenant model

Create a central `Tenant` or `Organization` model containing:

- id
- name
- legal_name
- slug
- institution_type
- logo and branding metadata
- timezone
- locale
- currency
- address
- contact information
- status
- subscription reference
- created_at
- updated_at

Every tenant-owned record must have a tenant relationship or an equally strong tenant boundary.

### Tenant isolation requirements

Tenant context must come from the authenticated user membership/session, never from an untrusted request body.

Every:

- query
- create operation
- update operation
- delete operation
- export
- background task
- report
- integration
- webhook-related operation

must be tenant-scoped.

Implement and test:

- cross-tenant object access prevention
- cross-tenant list filtering
- cross-tenant update prevention
- cross-tenant deletion prevention
- cross-tenant export prevention
- background-job tenant isolation
- IDOR protection

Use service-layer checks and queryset scoping. Consider PostgreSQL Row-Level Security as an additional defense for high-security deployments.

---

## 5. Identity, Membership, RBAC, and Permissions

Create a custom user model from the beginning.

Recommended entities:

- User
- Tenant
- Membership
- Role
- Permission
- RolePermission
- UserRole or MembershipRole
- Session/RefreshToken metadata
- AuditLog

A user may belong to multiple tenants with different roles.

### Core roles

- Super Admin
- Institution Admin
- Principal/Director
- Teacher/Faculty/Instructor
- Accountant
- Student/Learner
- Parent/Guardian
- Librarian
- Store Manager
- Transport Manager
- HR/Payroll role, if enabled

Use permission codes such as:

- `students.view`
- `students.create`
- `students.update`
- `students.delete`
- `attendance.mark`
- `attendance.correct`
- `marks.enter`
- `marks.review`
- `marks.publish`
- `fees.create_invoice`
- `fees.record_payment`
- `fees.refund`
- `users.manage_roles`
- `reports.export`

Implement both:

1. Role-level authorization
2. Object/resource-level authorization

Examples:

- Teachers can access only assigned classes, subjects, and learners.
- Parents can access only their linked children.
- Students can access only their own permitted records.
- Accountants can access financial data but not modify examination marks.
- Principals can review and approve selected workflows.
- Institution admins cannot access another tenant.
- Super admins must have clearly separated platform-level privileges.

Create an automated permission matrix and test it.

---

## 6. Suggested Django Project Structure

Use a structure similar to:

```text
backend/
├── manage.py
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── staging.py
│   │   └── production.py
│   ├── urls.py
│   ├── asgi.py
│   ├── wsgi.py
│   ├── celery.py
│   └── logging.py
├── apps/
│   ├── common/
│   ├── tenants/
│   ├── accounts/
│   ├── subscriptions/
│   ├── students/
│   ├── guardians/
│   ├── staff/
│   ├── academics/
│   ├── enrollments/
│   ├── attendance/
│   ├── examinations/
│   ├── finance/
│   ├── communications/
│   ├── learning/
│   ├── reports/
│   ├── inventory/
│   ├── integrations/
│   ├── audit/
│   └── notifications/
├── tests/
├── requirements/
├── docker/
├── scripts/
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

Keep domain logic out of oversized views and serializers. Use services, selectors/query modules, policies, and validators where useful.

---

## 7. Core Domain Models

Design and document relationships for at least:

### Platform and tenant

- Tenant
- SubscriptionPlan
- Subscription
- FeatureEntitlement
- UsageLimit
- TenantUsage
- Membership
- Role
- Permission

### People

- User
- Student/Learner
- Guardian
- StudentGuardian relationship
- Staff
- Department
- Employee document
- Leave record

### Academic structure

- AcademicYear/Session
- Term/Semester
- Program
- Department
- Course
- Subject
- Class/Cohort
- Batch
- Section/Division
- Room
- Teacher assignment
- Enrollment

### Academic operations

- AttendanceRecord
- AttendanceCorrectionRequest
- TimetableEntry
- Exam
- ExamSubject
- Mark
- GradeScale
- ResultPublication
- ReportCard

### Finance

- FeeCategory
- FeeStructure
- Scholarship
- Discount
- Invoice
- InvoiceLine
- Payment
- PaymentAllocation
- Refund
- Receipt
- ReconciliationRecord

### Communication and learning

- Announcement
- AudienceRule
- Notification
- MessageTemplate
- Assignment
- LearningResource
- Submission
- Feedback
- Event
- CalendarEntry

### Audit and integration

- AuditLog
- WebhookEvent
- IntegrationProvider
- SyncJob
- RetryRecord
- IdempotencyKey
- ExternalMapping

Add indexes and constraints based on real query patterns.

---

## 8. Core Business Workflows

Implement explicit state transitions and validations for:

### Admission

1. Admin starts admission.
2. Applicant and guardian details are entered.
3. Required documents are uploaded.
4. Duplicate records are checked.
5. Admission is reviewed and approved.
6. Admission number is generated.
7. Student is enrolled into academic year, class, and section.
8. Applicable fee structure is assigned.
9. Welcome notification is queued.
10. Audit events are recorded.

### Attendance

1. Teacher selects class, section, subject, and date.
2. System loads currently enrolled learners.
3. Teacher marks present, absent, late, excused, or half-day.
4. Duplicate attendance is prevented.
5. Submission is validated.
6. Correction requests follow an approval workflow.
7. Alerts and daily summaries are queued.
8. All changes are audited.

### Examinations

1. Authorized staff create an exam.
2. Exam subjects and schedules are configured.
3. Conflict checks are executed.
4. Assigned teachers enter marks.
5. Maximum and minimum marks are validated.
6. Marks are submitted for review.
7. Authorized staff approve and publish results.
8. Published results become protected from unauthorized edits.
9. Corrections require an auditable workflow.
10. Students and guardians can view only published permitted results.

### Fees and payments

1. Fee structures are configured.
2. Invoices are generated from enrollment and applicable rules.
3. Discounts and scholarships are validated.
4. Offline or online payments are recorded.
5. Payment transactions use idempotency.
6. Receipts are generated.
7. Outstanding balances are recalculated transactionally.
8. Webhooks are signature-verified.
9. Reconciliation reports are generated.
10. Refunds require authorization and audit logging.

---

## 9. API Design

Use versioned REST APIs:

```text
/api/v1/
```

Use consistent response and error formats.

Suggested endpoint groups:

```text
/api/v1/auth/
/api/v1/tenants/
/api/v1/memberships/
/api/v1/students/
/api/v1/guardians/
/api/v1/staff/
/api/v1/academics/
/api/v1/enrollments/
/api/v1/attendance/
/api/v1/timetables/
/api/v1/exams/
/api/v1/marks/
/api/v1/results/
/api/v1/fees/
/api/v1/invoices/
/api/v1/payments/
/api/v1/announcements/
/api/v1/notifications/
/api/v1/assignments/
/api/v1/reports/
/api/v1/audit-logs/
```

Every endpoint must specify:

- authentication requirement
- required permissions
- tenant scope
- request schema
- response schema
- validation rules
- pagination behavior
- filtering and sorting
- error responses
- audit behavior
- rate-limit requirements

Use pagination for list endpoints. Support filtering, search, sorting, and safe exports.

---

## 10. Security Requirements

Implement and document:

- secure password hashing using Django-supported strong hashing
- short-lived access tokens
- refresh-token rotation and revocation
- secure HTTP-only cookies where applicable
- CSRF protection where cookie authentication is used
- HTTPS in production
- CORS allowlist
- rate limiting for login, password reset, OTP, exports, and sensitive actions
- brute-force protection
- input validation
- safe file upload validation
- MIME type and file-size restrictions
- private object storage URLs
- prevention of injection and XSS
- secure headers
- secrets only in environment variables or secret manager
- least-privilege database credentials
- audit logging for sensitive changes
- privacy-aware data retention and deletion
- backup encryption and restoration testing

Do not store unnecessary sensitive or child-related information. Medical notes and other sensitive fields must be optional, access-controlled, and legally reviewed for the deployment jurisdiction.

---

## 11. Error Handling, Observability, and Audit

Implement:

- centralized DRF exception handling
- stable machine-readable error codes
- correlation/request IDs
- structured logs
- error tracking using Sentry or equivalent
- health endpoint
- readiness endpoint
- Celery task failure logging
- integration failure logging
- audit trail for sensitive operations

Audit at least:

- role and permission changes
- student record edits
- mark changes
- result publication
- fee edits
- payments
- refunds
- discounts
- exports
- configuration changes
- account status changes
- admission approval
- attendance corrections

Never log passwords, tokens, payment secrets, or sensitive personal data unnecessarily.

---

## 12. Background Jobs

Use Celery and Redis for:

- notifications
- email/SMS/WhatsApp adapters
- report generation
- bulk imports
- scheduled reminders
- payment reconciliation
- external synchronization
- AI processing
- low-stock alerts
- attendance alerts

Every task must:

- carry tenant context safely
- be idempotent where possible
- have retries with backoff
- avoid duplicate processing
- log failures
- preserve auditability
- avoid trusting tenant IDs from unvalidated payloads

---

## 13. External Integration Design

Create provider interfaces/adapters for:

- payment providers
- email
- SMS
- WhatsApp
- AI services
- video conferencing
- object storage
- supplier APIs
- GPS/transport services

Include:

- provider configuration
- external ID mapping
- webhook verification
- idempotency keys
- retry strategy
- dead-letter or failed-event handling
- sync status
- integration logs
- provider replacement without changing domain logic

---

## 14. Testing Strategy

Create automated tests for:

### Unit tests

- validators
- fee calculations
- grading rules
- attendance calculations
- permission policies
- state transitions
- duplicate detection

### Integration tests

- API authentication
- tenant-scoped querysets
- database constraints
- transactions
- payment processing
- webhook handling
- file uploads

### Security tests

- unauthenticated access
- unauthorized role access
- cross-tenant access
- IDOR
- mass assignment
- injection attempts
- CSRF/session handling
- unsafe file uploads
- export access
- background task isolation

### End-to-end workflow tests

- admission
- attendance
- examination and publication
- fee payment and reconciliation
- announcements
- assignments
- reports

The project must not be considered complete until the permission matrix and cross-tenant isolation tests pass.

---

## 15. Version Control and Codebase Audit Gate

Before changing an existing codebase, act as a senior developer conducting an audit. Do not modify files during the audit.

Check:

### Version control

- Is Git initialized?
- Is there a real commit history?
- Is `.gitignore` present and correct?
- Are secrets excluded?
- Are branches and commit messages meaningful?
- Are migrations, environment templates, and documentation tracked?

If Git is missing, explain how to initialize it properly, create the first clean commit, and protect secrets.

### Duplicate and dead code

Find:

- duplicated functions
- repeated API calls
- copy-pasted serializers/views/services
- repeated permission logic
- unused models
- unused endpoints
- unused imports
- dead feature flags
- duplicate validation rules
- repeated frontend/backend business logic

For every finding, report the file path, location, impact, and recommended consolidation.

### Hardcoded secrets

Scan every file for:

- API keys
- passwords
- JWT secrets
- database credentials
- cloud credentials
- webhook secrets
- private tokens

List every affected file and recommend environment-variable migration. Never print the full secret value in the report.

### Documentation

Check for:

- README
- setup instructions
- architecture overview
- data-flow explanation
- environment variable documentation
- migration instructions
- deployment guide
- API documentation
- troubleshooting guide

If missing, generate documentation based on the actual codebase rather than assumptions.

### Error tracking

Check whether real runtime errors would be visible through:

- Sentry
- centralized logging
- structured logs
- alerting
- task failure monitoring
- health checks

If absent, recommend the simplest reliable implementation.

### Access control

List every location where one user's data might be read, modified, exported, or deleted by another user. Verify:

- tenant scoping
- role permissions
- object-level ownership
- queryset filtering
- serializer validation
- service-layer checks
- background task checks
- export authorization
- file URL authorization

Report each weakness with severity, affected endpoint/file, exploit scenario, and remediation.

---

## 16. Delivery Phases

### Phase 1 — Foundation

- repository setup
- environment configuration
- Docker
- PostgreSQL
- custom user model
- tenant model
- memberships
- authentication
- RBAC
- audit logging
- API versioning
- CI checks

### Phase 2 — Core records

- students
- guardians
- staff
- departments
- academic years
- terms
- classes
- sections
- subjects
- enrollments

### Phase 3 — Academic operations

- attendance
- timetable
- examinations
- marks
- grades
- result publication
- report cards

### Phase 4 — Finance

- fee structures
- invoices
- payments
- receipts
- discounts
- scholarships
- refunds
- reconciliation

### Phase 5 — Communication and learning

- announcements
- notifications
- events
- assignments
- resources
- submissions
- feedback

### Phase 6 — Reports and hardening

- dashboards
- PDF/CSV exports
- performance optimization
- security testing
- monitoring
- backups
- recovery
- deployment manuals

### Phase 7 — Optional modules

- library
- transport
- hostel
- inventory
- HR/payroll
- AI insights
- online learning
- external integrations

---

## 17. Required Deliverables

Produce:

- architecture overview
- domain/module map
- ER diagram
- database dictionary
- permission matrix
- API endpoint catalog
- OpenAPI schema
- workflow documentation
- environment variable reference
- local setup guide
- staging/production deployment guide
- backup and recovery guide
- test plan
- security checklist
- audit logging specification
- integration strategy
- known limitations
- maintenance guide
- handoff README

---

## 18. Definition of Done

A module is complete only when:

- database models and constraints exist
- migrations are created and tested
- serializers validate input
- permissions are enforced server-side
- tenant isolation is tested
- business rules are covered by tests
- API documentation is available
- errors use consistent responses
- audit events are implemented where required
- pagination/filtering is implemented
- logs and monitoring are adequate
- no secrets are hardcoded
- documentation is updated
- CI checks pass
- the feature is reviewed against the acceptance criteria

Build securely, document decisions, and prioritize correctness over speed.
