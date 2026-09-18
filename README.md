# OmniEducationalManagement — Multi-Tenant Educational SaaS Backend

[![Python Version](https://img.shields.io/badge/python-3.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-6.1-green.svg)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.18-red.svg)](https://www.django-rest-framework.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://www.postgresql.org/)
[![Celery](https://img.shields.io/badge/Celery-5.6-brightgreen.svg)](https://docs.celeryq.dev/)
[![Redis](https://img.shields.io/badge/Redis-7-red.svg)](https://redis.io/)
[![License](https://img.shields.io/badge/License-Proprietary-black.svg)]()

A production-ready, highly secure, modular multi-tenant Educational SaaS backend engineered with **Django REST Framework**, **PostgreSQL**, **Redis**, and **Celery**.

The platform is designed as an enterprise **Modular Monolith** supporting:
- Schools (K-12)
- Colleges & Higher Secondary
- Universities & Multi-faculty Campuses
- Professional Training Institutes
- Coaching Centers & Academies
- Online Tuition & EdTech Learning Providers

---

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Domain & Module Map](#2-domain--module-map)
3. [Entity-Relationship Diagram](#3-entity-relationship-diagram)
4. [Multi-Tenant Isolation Strategy](#4-multi-tenant-isolation-strategy)
5. [RBAC & Granular Permission Matrix](#5-rbac--granular-permission-matrix)
6. [API Endpoint Catalog](#6-api-endpoint-catalog)
7. [Core Business Workflows](#7-core-business-workflows)
8. [Audit Logging Specification](#8-audit-logging-specification)
9. [Background Processing with Celery](#9-background-processing-with-celery)
10. [Environment Variables Reference](#10-environment-variables-reference)
11. [Local Development Setup](#11-local-development-setup)
12. [Production Deployment Guide](#12-production-deployment-guide)
13. [Backup, Restore & Disaster Recovery](#13-backup-restore--disaster-recovery)
14. [Automated Test Suite & Verification](#14-automated-test-suite--verification)
15. [Security Checklist & Compliance](#15-security-checklist--compliance)

---

## 1. Architecture Overview

OmniEducationalManagement follows a clean, layered **Modular Monolith** design. It prioritizes business rule enforcement on the backend and treats untrusted client inputs with zero trust.

```
                              ┌───────────────────────────────────┐
                              │    Frontend / Client Applications │
                              │   (SPA, Mobile Apps, Portals)     │
                              └─────────────────┬─────────────────┘
                                                │ HTTPS + JWT Bearer
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ Django REST Framework Backend Core                                                          │
│                                                                                             │
│  [Middleware Pipeline]                                                                      │
│  ├── RequestIDMiddleware        ──► Generates/propagates X-Request-ID for tracing          │
│  ├── Security & CORS Middleware ──► Enforces strict headers and origin allowlists           │
│  ├── TenantContextMiddleware    ──► Resolves & verifies tenant membership from JWT          │
│  └── Centralized ExceptionHandler──► Normalizes all responses into standard JSON envelope  │
│                                                                                             │
│  [Domain Modules (Apps)]                                                                    │
│  ├── common/        ├── accounts/     ├── tenants/      ├── academics/                      │
│  ├── students/      ├── guardians/    ├── staff/        ├── enrollments/                    │
│  ├── attendance/    ├── examinations/ ├── finance/      ├── communications/                 │
│  └── audit/                                                                                 │
│                                                                                             │
│  [Tenant Isolation Layer]                                                                   │
│  ├── TenantScopedModel          ──► Automatically injects tenant foreign key                │
│  ├── TenantManager & QuerySet   ──► Automatically filters: WHERE tenant_id = current_tenant │
│  └── HasTenantPermission        ──► Server-side RBAC verification per tenant context        │
└──────────────────────────────┬────────────────────────────────┬─────────────────────────────┘
                               │                                │
                               ▼                                ▼
                 ┌───────────────────────────┐    ┌───────────────────────────┐
                 │    PostgreSQL Database    │    │      Redis & Celery       │
                 │ (UUID PKs, RLS, Cascades) │    │(Background Tasks, Queues) │
                 └───────────────────────────┘    └───────────────────────────┘
```

### Standard JSON Response Format
All API responses follow a uniform structure:
```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "count": 50,
    "current_page": 1,
    "page_size": 25,
    "request_id": "c1f7b7b1-...",
    "timestamp": "2026-09-18T16:40:00Z"
  }
}
```

---

## 2. Domain & Module Map

| Module App | Domain Responsibility |
| :--- | :--- |
| `apps.common` | Base models (`UUIDModel`, `TimeStampedModel`, `SoftDeletableModel`, `TenantScopedModel`), thread-safe context, middlewares, standard exceptions, pagination. |
| `apps.tenants` | Central `Tenant` organization entity, institution types, status management, branding, localization. |
| `apps.accounts` | Custom `User` model, multi-tenant `Membership`, `Role`, `Permission`, JWT token issuance and rotation, tenant switching. |
| `apps.audit` | Immutable compliance `AuditLog`, automatic request/actor capture, before-and-after diff tracking. |
| `apps.academics` | `AcademicYear`, `Term`, `Department`, `Course`, `Subject`, `ClassCohort`, and `Section`. |
| `apps.students` | `Student` profiles, multi-step admission workflow, duplicate detection, medical notes protection. |
| `apps.guardians` | `Guardian` records, child-guardian relationships, emergency contacts. |
| `apps.staff` | `Staff` faculty and administrative records, employee IDs, department assignments. |
| `apps.enrollments` | Student class and section enrollments per academic year, roll numbers. |
| `apps.attendance` | Daily/subject attendance, batch marking, duplicate prevention, attendance correction request workflow. |
| `apps.examinations` | `Exam`, schedules, marks entry, max mark constraints, result publication workflow, post-publication immutability lock. |
| `apps.finance` | `FeeCategory`, `FeeStructure`, `Invoice`, `InvoiceLine`, `Payment` with idempotency, receipts, balance calculations. |
| `apps.communications` | Targeted `Announcement` broadcasting and `Notification` dispatches. |

---

## 3. Entity-Relationship Diagram

```mermaid
erDiagram
    TENANT ||--o{ MEMBERSHIP : has
    USER ||--o{ MEMBERSHIP : holds
    MEMBERSHIP ||--o{ MEMBERSHIP_ROLE : assigned
    ROLE ||--o{ MEMBERSHIP_ROLE : grants
    ROLE ||--o{ ROLE_PERMISSION : contains
    PERMISSION ||--o{ ROLE_PERMISSION : granted_by

    TENANT ||--o{ STUDENT : owns
    TENANT ||--o{ STAFF : employs
    TENANT ||--o{ ACADEMIC_YEAR : configures
    ACADEMIC_YEAR ||--o{ CLASS_COHORT : contains
    CLASS_COHORT ||--o{ SECTION : divides
    
    STUDENT ||--o{ ENROLLMENT : registers
    CLASS_COHORT ||--o{ ENROLLMENT : accepts
    SECTION ||--o{ ENROLLMENT : assigns
    
    STUDENT ||--o{ STUDENT_GUARDIAN : linked_to
    GUARDIAN ||--o{ STUDENT_GUARDIAN : cares_for

    SECTION ||--o{ ATTENDANCE_RECORD : records
    STUDENT ||--o{ ATTENDANCE_RECORD : marked_for

    CLASS_COHORT ||--o{ EXAM : schedules
    EXAM ||--o{ EXAM_SUBJECT : details
    EXAM_SUBJECT ||--o{ MARK : contains
    STUDENT ||--o{ MARK : obtains

    STUDENT ||--o{ INVOICE : billed
    INVOICE ||--o{ INVOICE_LINE : items
    INVOICE ||--o{ PAYMENT : collects

    TENANT ||--o{ AUDIT_LOG : tracks
```

---

## 4. Multi-Tenant Isolation Strategy

1. **Context Resolution**: The active tenant is extracted from the `X-Tenant-ID` header (or defaulted to the user's primary membership) and **verified against database memberships**. If a user tries to access a tenant they do not belong to, the middleware halts execution with a `403 Forbidden` (`CROSS_TENANT_FORBIDDEN`).
2. **Model Layer**: All tenant data models inherit from `TenantScopedModel`. The custom `TenantManager` automatically restricts queries to `WHERE tenant_id = <current_tenant>`.
3. **Defense-in-Depth**:
   - DRF ViewSets filter `get_queryset()` by `request.tenant`.
   - Serializers inject `tenant=request.tenant` during creation.
   - Cross-tenant updates and deletes return `404 Not Found` (IDOR protection).

---

## 5. RBAC & Granular Permission Matrix

| Role | Students | Attendance | Examinations | Finance | Academics | Audit Logs |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Super Admin** | Full | Full | Full | Full | Full | All Tenants |
| **Institution Admin** | Full | Full | Full | Full | Full | Tenant Scoped |
| **Principal / Director** | Full | Approve Corrections | Publish Results | View Reports | Manage | Tenant Scoped |
| **Teacher / Faculty** | View Only | Mark / Request Correction | Enter Marks | Forbidden | View Only | Forbidden |
| **Accountant** | View Only | Forbidden | Forbidden | Full | View Only | Forbidden |
| **Student** | Own Profile | Own Record | Own Published Results | Own Invoices | View Own | Forbidden |
| **Parent / Guardian** | Linked Children | Linked Children | Published Results | Linked Invoices | View Linked | Forbidden |

---

## 6. API Endpoint Catalog

Base URL: `/api/v1/`

### System & Health Probes
- `GET /api/v1/health/` — Application liveness probe
- `GET /api/v1/ready/` — Database readiness probe
- `GET /api/v1/schema/` — OpenAPI 3.0 schema YAML/JSON
- `GET /api/v1/docs/` — Swagger UI documentation
- `GET /api/v1/redoc/` — ReDoc documentation

### Authentication & Memberships
- `POST /api/v1/auth/register-institution/` — Public onboarding (registers tenant + admin)
- `POST /api/v1/auth/login/` — Issues JWT access and refresh tokens
- `POST /api/v1/auth/refresh/` — Rotates/refreshes JWT access token
- `GET /api/v1/auth/me/` — Current user profile, active tenant, active permissions
- `POST /api/v1/auth/switch-tenant/` — Switches default active organization
- `GET /api/v1/memberships/` — Tenant membership list
- `GET /api/v1/roles/` — Tenant role catalog
- `GET /api/v1/permissions/` — Platform permission catalog

### Academic Structure
- `GET, POST /api/v1/academics/years/` — Academic sessions
- `GET, POST /api/v1/academics/terms/` — Academic terms/semesters
- `GET, POST /api/v1/academics/departments/` — Academic departments
- `GET, POST /api/v1/academics/courses/` — Academic degree programs/courses
- `GET, POST /api/v1/academics/subjects/` — Academic subjects
- `GET, POST /api/v1/academics/classes/` — Class cohorts / standards
- `GET, POST /api/v1/academics/sections/` — Sections / divisions

### Students & Admissions
- `GET /api/v1/students/` — List students (filtered by status, gender, blood group)
- `GET, PATCH, DELETE /api/v1/students/{id}/` — Student details and soft deletion
- `POST /api/v1/students/admit/` — Atomic multi-step student admission workflow

### Attendance
- `GET /api/v1/attendance/records/` — View attendance records
- `POST /api/v1/attendance/records/bulk-mark/` — Bulk mark attendance for a class section
- `GET, POST /api/v1/attendance/corrections/` — Attendance correction requests
- `POST /api/v1/attendance/corrections/{id}/approve/` — Approve correction
- `POST /api/v1/attendance/corrections/{id}/reject/` — Reject correction

### Examinations & Grading
- `GET, POST /api/v1/exams/grade-scales/` — Grade point scale rules
- `GET, POST /api/v1/exams/exams/` — Scheduled exams
- `POST /api/v1/exams/exams/{id}/publish/` — Publish results & lock marks
- `GET, POST /api/v1/exams/schedules/` — Exam timetable schedules
- `GET, POST, PATCH /api/v1/exams/marks/` — Enter and update marks (pre-publication only)

### Finance & Payments
- `GET, POST /api/v1/finance/categories/` — Fee categories
- `GET, POST /api/v1/finance/structures/` — Fee structures
- `GET /api/v1/finance/invoices/` — Invoices
- `POST /api/v1/finance/invoices/generate/` — Generate invoice from fee structures
- `GET /api/v1/finance/payments/` — Payment transactions
- `POST /api/v1/finance/payments/record/` — Process payment with idempotency key

### Communications & Audit
- `GET, POST /api/v1/communications/announcements/` — Broadcast announcements
- `GET, POST /api/v1/communications/notifications/` — In-app notifications
- `GET /api/v1/audit/` — Tenant-scoped audit logs

---

## 7. Core Business Workflows

### 7.1 Admission Workflow
1. Client submits student bio, optional guardian details, and optional enrollment target to `POST /api/v1/students/admit/`.
2. System checks duplicate admission number and `(first_name, last_name, DOB)` within the tenant.
3. Student record is created.
4. If guardian details provided, `Guardian` and `StudentGuardian` links are created.
5. If academic year, class, and section provided, student is enrolled and status updated to `enrolled`.
6. Audit event is written transactionally.

### 7.2 Examination & Immutability Lock Workflow
1. Exam and subject schedules are configured with `max_marks` and `passing_marks`.
2. Teachers submit marks: system validates `0 <= marks_obtained <= max_marks`.
3. Marks are reviewed by department heads.
4. Principal/Admin publishes exam via `POST /api/v1/exams/exams/{id}/publish/`.
5. Exam `is_published` becomes `True`.
6. Subsequent attempts to modify marks throw validation errors.
7. Students and parents are granted read access only to published results.

### 7.3 Invoicing & Idempotent Payment Workflow
1. Admin generates invoice from active fee structures via `POST /api/v1/finance/invoices/generate/`.
2. System calculates `total_amount`, applies `discount_amount`, and records `balance_amount`.
3. Client submits payment to `POST /api/v1/finance/payments/record/` with an `idempotency_key`.
4. System executes `select_for_update()` on invoice to prevent concurrent balance corruption.
5. If payment with identical `idempotency_key` exists, it returns the existing record safely without double-charging.
6. System deducts invoice balance. When balance reaches `0.00`, invoice status updates to `PAID`.

---

## 8. Audit Logging Specification

Critical platform mutations automatically create immutable `AuditLog` records storing:
- `tenant`: Target institution
- `actor`: Authenticated user who performed the action
- `action`: `CREATE`, `UPDATE`, `DELETE`, `PUBLISH`, `APPROVE`, `REJECT`
- `resource_type` and `resource_id`: Target entity
- `changes`: JSON diff showing before-and-after states
- `ip_address`: Client IP (respecting `X-Forwarded-For`)
- `request_id`: Tracing correlation ID

---

## 9. Background Processing with Celery

Celery 5.6 and Redis 7 are configured for asynchronous background processing:
- Configuration: `config/celery.py`
- Worker Command: `celery -A config worker --loglevel=info`
- Beat Scheduler: `celery -A config beat --loglevel=info`

Tasks automatically inherit tenant scoping by requiring `tenant_id` in task signatures and validating boundaries before execution.

---

## 10. Environment Variables Reference

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `DJANGO_SETTINGS_MODULE` | `config.settings.development` | Active settings file |
| `DJANGO_SECRET_KEY` | *(required in prod)* | Django cryptographic secret key |
| `DJANGO_DEBUG` | `False` | Debug mode toggle |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Permitted Host headers |
| `DATABASE_URL` | `postgres://user:pass@host:5432/db` | PostgreSQL connection string |
| `USE_SQLITE_FOR_LOCAL` | `False` | Fallback to SQLite for lightweight local dev |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis caching & broker URL |
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` | Celery message broker |
| `JWT_SECRET_KEY` | *(same as secret key)* | Secret key for JWT signing |
| `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` | `60` | JWT access token lifespan |
| `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | `7` | JWT refresh token lifespan |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | Whitelisted frontend origins |
| `SENTRY_DSN` | *(empty)* | Sentry exception tracking DSN |

---

## 11. Local Development Setup

```bash
# 1. Activate virtual environment
.\env\Scripts\activate

# 2. Install requirements
pip install -r requirements/local.txt

# 3. Apply database migrations
python manage.py migrate

# 4. Run development server
python manage.py runserver 0.0.0.0:8000

# 5. Run Celery background worker (in a separate terminal)
celery -A config worker --loglevel=info

# 6. Run Celery periodic beat scheduler (in a separate terminal)
celery -A config beat --loglevel=info
```

---

## 12. Production Deployment Guide

1. **WSGI Server**: Run via Gunicorn:
   ```bash
   gunicorn --bind 0.0.0.0:8000 --workers 4 --threads 2 config.wsgi:application
   ```
2. **Reverse Proxy (Nginx)**: Configure SSL termination, HTTP/2, and proxy headers:
   ```nginx
   proxy_set_header Host $host;
   proxy_set_header X-Real-IP $remote_addr;
   proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
   proxy_set_header X-Forwarded-Proto $scheme;
   ```
3. **Environment**: Set `DJANGO_SETTINGS_MODULE=config.settings.production` and `DJANGO_DEBUG=False`.

---

## 13. Backup, Restore & Disaster Recovery

### Automated PostgreSQL Backup
```bash
# Dump database with timestamp
pg_dump -U omni_user -h localhost -d omni_db -F c -b -v -f "omni_backup_$(date +%Y%m%d_%H%M%S).dump"
```

### Restoration Procedure
```bash
# Restore into fresh database
pg_restore -U omni_user -h localhost -d omni_db -v -c "omni_backup_20260918.dump"
```

---

## 14. Automated Test Suite & Verification

The test suite validates security, RBAC, tenant isolation, and workflows:
```bash
# Run pytest with timing report
pytest -v
```

### Test Coverage Summary
- `test_cross_tenant_isolation.py`: Verified that Tenant A cannot query, detail, update, or delete Tenant B data. Verified header spoofing rejection.
- `test_rbac_permissions.py`: Verified permission matrix boundaries for Teacher, Accountant, and Admin.
- `test_auth_and_tokens.py`: Verified institution registration, JWT token generation, refresh, and tenant switching.
- `test_workflows.py`: Verified end-to-end Admission, Attendance batch marking, Exam publication locking, and Idempotent Payments.
- `test_audit_logging.py`: Verified that domain events write immutable records.

---

## 15. Security Checklist & Compliance

- [x] **No Plaintext Secrets**: Passwords hashed using PBKDF2/Argon2. Secrets read from environment variables.
- [x] **Multi-Tenant Scoping**: All queries scoped by authenticated user's verified tenant membership.
- [x] **IDOR Protection**: Object lookups return 404 if object belongs to another tenant.
- [x] **Idempotent Payments**: Payment processing protects against network re-transmissions.
- [x] **Result Publication Lock**: Exam marks become immutable once results are published.
- [x] **Correlation Tracing**: `X-Request-ID` attached to all incoming and outgoing requests.
- [x] **Audit Trail**: Sensitive operations recorded with before/after diffs.