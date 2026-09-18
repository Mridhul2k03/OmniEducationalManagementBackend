# OmniEducationalManagement SaaS — REST API Documentation

**Version:** `v1.0.0`  
**Base URL:** `http://127.0.0.1:8000/api/v1/`  
**OpenAPI Swagger UI:** [http://127.0.0.1:8000/api/v1/docs/](http://127.0.0.1:8000/api/v1/docs/)  
**OpenAPI ReDoc:** [http://127.0.0.1:8000/api/v1/redoc/](http://127.0.0.1:8000/api/v1/redoc/)  
**OpenAPI Schema (YAML):** [http://127.0.0.1:8000/api/v1/schema/](http://127.0.0.1:8000/api/v1/schema/)

---

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Multi-Tenancy & Headers](#2-multi-tenancy--headers)
3. [Authentication Schemes](#3-authentication-schemes)
   - [Cookie Authentication (HttpOnly)](#31-cookie-authentication-httponly)
   - [Bearer JWT Token Authentication](#32-bearer-jwt-token-authentication)
4. [Standard Envelopes & Error Handling](#4-standard-envelopes--error-handling)
5. [Pagination Specification](#5-pagination-specification)
6. [API Endpoints Reference](#6-api-endpoints-reference)
   - [1. Health & Liveness Probes](#61-health--liveness-probes)
   - [2. Identity, Auth & RBAC](#62-identity-auth--rbac)
   - [3. Tenants & Institutions](#63-tenants--institutions)
   - [4. Students & Admissions](#64-students--admissions)
   - [5. Staff & Faculty](#65-staff--faculty)
   - [6. Academic Structure](#66-academic-structure)
   - [7. Attendance Tracking](#67-attendance-tracking)
   - [8. Examinations & Grading](#68-examinations--grading)
   - [9. Finance, Invoicing & Payments](#69-finance-invoicing--payments)
   - [10. Communications & Bulletins](#610-communications--bulletins)
   - [11. Audit Logging](#611-audit-logging)

---

## 1. Architecture Overview

OmniEducationalManagement is a multi-tenant Educational SaaS platform. Every tenant represents an educational institution (K-12 School, College, University, or Coaching Institute) with isolated data scopes, custom terminology, and role-based permissions.

- **Protocol:** HTTP / HTTPS
- **Data Format:** JSON (`application/json`)
- **Encoding:** UTF-8
- **Date/Time Standard:** ISO 8601 UTC (`YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SSZ`)

---

## 2. Multi-Tenancy & Headers

All tenant-scoped requests must identify their institutional context via the `X-Tenant-ID` header.

| Header Name | Type | Description |
|---|---|---|
| `X-Tenant-ID` | String | Either tenant **UUID** (e.g. `7d18388a-872b-4d2b-b42a-f658c03e9e60`) or **Slug** (e.g. `oxford-crest`). |
| `X-Request-ID` | UUID (Optional) | Unique client request identifier for tracing in audit logs. |

### Fallback Behavior:
If `X-Tenant-ID` is omitted or empty:
1. For authenticated users, the system checks the user's active/default tenant membership.
2. If none is resolved, the system selects the primary active institution.
3. For public registration or platform-level endpoints, `X-Tenant-ID` is optional.

---

## 3. Authentication Schemes

The backend supports two complementary authentication modes:

### 3.1 Cookie Authentication (HttpOnly)
Recommended for browser clients (Vite / React / Next.js).
- When logging in via `POST /api/v1/auth/login/`, the backend sets two secure HttpOnly cookies:
  - `access_token` (Lifetime: 60 minutes, `Path=/`, `SameSite=Lax`, `HttpOnly`)
  - `refresh_token` (Lifetime: 7 days, `Path=/`, `SameSite=Lax`, `HttpOnly`)
- All subsequent fetch requests made with `credentials: "include"` automatically send the `access_token` cookie.
- Token refresh (`POST /api/v1/auth/refresh/`) reads the `refresh_token` cookie and issues a new `access_token` cookie.
- Logout (`POST /api/v1/auth/logout/`) deletes all authentication cookies.

### 3.2 Bearer JWT Token Authentication
Standard for mobile applications, external microservices, and scripts.
- Header: `Authorization: Bearer <access_token>`

---

## 4. Standard Envelopes & Error Handling

### 4.1 Success Response Envelope
```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "request_id": "34ceacc9-080f-4b97-9248-27d85547a712"
  }
}
```

### 4.2 Error Response Envelope
```json
{
  "success": false,
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "No active account found with the given credentials",
    "details": null
  },
  "meta": {
    "request_id": "a9649d33-12bb-43b1-a3f4-4c70a3625cc6"
  }
}
```

### 4.3 Standard Error Codes:
- `INVALID_CREDENTIALS` — Incorrect username or password.
- `NOT_AUTHENTICATED` — Missing or expired token/cookie.
- `PERMISSION_DENIED` — User does not possess the required tenant permission.
- `INVALID_TENANT_ID` — The specified tenant does not exist.
- `VALIDATION_ERROR` — Input data validation failed (details object contains field errors).
- `NOT_FOUND` — Requested entity was not found in the current tenant.

---

## 5. Pagination Specification

All collection listing endpoints use `StandardResultsSetPagination`:

### Query Parameters:
- `page` (Integer, default: `1`): Page number.
- `page_size` (Integer, default: `25`, max: `100`): Items per page.

### Response Format:
```json
{
  "success": true,
  "data": [ ... ],
  "meta": {
    "count": 142,
    "total_pages": 6,
    "current_page": 1,
    "page_size": 25,
    "next": "http://127.0.0.1:8000/api/v1/students/?page=2",
    "previous": null,
    "request_id": "e924f4ec-fa2d-454b-b865-b3c1f7666e91"
  }
}
```

---

## 6. API Endpoints Reference

### 6.1 Health & Liveness Probes

#### `GET /api/v1/health/`
Checks backend database and caching health.
- **Auth:** None (Public)
- **Response:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "database": "operational",
    "timestamp": "2026-09-18T18:00:00Z"
  }
}
```

#### `GET /api/v1/ready/`
Kubernetes/Docker readiness probe.

---

### 6.2 Identity, Auth & RBAC

#### `POST /api/v1/auth/login/`
Authenticates user, issues JWT tokens, and sets HttpOnly auth cookies.
- **Auth:** None
- **Request Body:**
```json
{
  "email": "eleanor.vance@omni-edu.org",
  "password": "Password123!"
}
```
- **Response (`200 OK`):**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsIn...",
  "refresh": "eyJhbGciOiJIUzI1NiIsIn...",
  "user": {
    "id": "e6d87266-a9c3-4f87-9a52-5270f460bc5c",
    "email": "eleanor.vance@omni-edu.org",
    "first_name": "Eleanor",
    "last_name": "Vance",
    "full_name": "Eleanor Vance",
    "is_staff": true
  },
  "accessible_tenants": [
    {
      "id": "7d18388a-872b-4d2b-b42a-f658c03e9e60",
      "name": "Oxford Crest University",
      "slug": "oxford-crest",
      "institution_type": "university_college",
      "is_default": true
    }
  ],
  "active_tenant": {
    "id": "7d18388a-872b-4d2b-b42a-f658c03e9e60",
    "name": "Oxford Crest University",
    "slug": "oxford-crest"
  }
}
```
- **Headers Returned:**
  - `Set-Cookie: access_token=...; HttpOnly; Path=/; SameSite=Lax`
  - `Set-Cookie: refresh_token=...; HttpOnly; Path=/; SameSite=Lax`

#### `POST /api/v1/auth/refresh/`
Refreshes the access token using request body or `refresh_token` cookie.
- **Request Body (Optional if cookie present):**
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsIn..."
}
```

#### `POST /api/v1/auth/logout/`
Clears all authentication cookies.
- **Response (`200 OK`):**
```json
{
  "success": true,
  "message": "Logged out successfully."
}
```

#### `GET /api/v1/auth/me/`
Retrieves current user identity, permissions, and active memberships.
- **Auth:** Cookie or Bearer Token

#### `POST /api/v1/auth/switch-tenant/`
Switches active tenant membership context.
- **Request Body:**
```json
{
  "tenant_id": "7d18388a-872b-4d2b-b42a-f658c03e9e60"
}
```

#### `POST /api/v1/auth/register-institution/`
Onboarding endpoint to create a new institution tenant and primary admin.
- **Request Body:**
```json
{
  "institution_name": "Cambridge Academy",
  "slug": "cambridge-academy",
  "institution_type": "k12_school",
  "admin_first_name": "Charles",
  "admin_last_name": "Darwin",
  "admin_email": "admin@cambridge-academy.edu",
  "admin_password": "Password123!"
}
```

---

### 6.3 Tenants & Institutions

#### `GET /api/v1/tenants/`
Lists all institutions accessible to current user.

#### `GET /api/v1/tenants/current/`
Returns detailed configuration, features, and terminology for active tenant.

---

### 6.4 Students & Admissions

#### `GET /api/v1/students/`
Lists learners enrolled in active tenant.
- **Query Filters:**
  - `search` (Search by admission number, first name, last name)
  - `status` (`admitted`, `enrolled`, `suspended`, `graduated`, `withdrawn`)
  - `gender` (`M`, `F`, `O`)
  - `ordering` (`admission_number`, `-created_at`)

#### `POST /api/v1/students/admit/`
Executes complete student admission lifecycle:
1. Validates duplicate records.
2. Creates Student profile.
3. Automatically creates `User` credentials with `student` role (`Student123!`).
4. Links Guardian profile via `StudentGuardian`.
5. Enrolls student into academic year, cohort, and section.
6. Generates initial tuition fee invoice in finance.
7. Dispatches welcome in-app notification.
8. Logs immutable audit trail.

- **Request Body:**
```json
{
  "first_name": "Mira",
  "last_name": "Kowalski",
  "email": "mira.kowalski@omni-edu.org",
  "date_of_birth": "2006-03-22",
  "gender": "F",
  "admission_date": "2026-09-18",
  "admission_number": "ADM-2026-0015",
  "class_name": "Year 3 Computer Science",
  "section_name": "Section A",
  "guardian": {
    "first_name": "Jan",
    "last_name": "Kowalski",
    "phone_number": "+15559876543",
    "relationship": "father"
  }
}
```
- **Response (`201 Created`):**
```json
{
  "success": true,
  "message": "Student 'Mira Kowalski' admitted successfully.",
  "data": {
    "id": "18d23f73-f065-4706-b31c-71efc2a08cc3",
    "admission_number": "ADM-2026-0015",
    "first_name": "Mira",
    "last_name": "Kowalski",
    "full_name": "Mira Kowalski",
    "email": "mira.kowalski@omni-edu.org",
    "user_id": "9342b5cb-1457-41ab-8588-46603a1104e9",
    "class_cohort_name": "Year 3 Computer Science",
    "section_name": "Section A",
    "date_of_birth": "2006-03-22",
    "gender": "F",
    "status": "enrolled",
    "guardian_links": [
      {
        "id": "b4fa957f-41d1-4ffc-a00e-dce214194d3b",
        "guardian_name": "Jan",
        "relationship": "father",
        "phone_number": "+15559876543",
        "is_primary": true
      }
    ]
  }
}
```

#### `GET /api/v1/students/{id}/`
Retrieves detailed student profile.

#### `PATCH /api/v1/students/{id}/`
Updates student fields (e.g. emergency contact, blood group, status).

#### `DELETE /api/v1/students/{id}/`
Soft-deletes student record (`204 No Content`).

---

### 6.5 Staff & Faculty

#### `GET /api/v1/staff/`
Lists faculty and staff members.
- **Filters:** `search`, `department`, `employment_type`, `status`

#### `POST /api/v1/staff/`
Creates a new staff member.
- **Request Body:**
```json
{
  "employee_id": "EMP-2026-001",
  "user": "e6d87266-a9c3-4f87-9a52-5270f460bc5c",
  "department": "b3957d94-6b76-43b4-ba2b-1e463462d09b",
  "designation": "Assistant Professor",
  "qualification": "M.Sc. Computer Science",
  "joined_date": "2026-08-01",
  "employment_type": "full_time"
}
```

---

### 6.6 Academic Structure

#### `GET /api/v1/academics/years/` — Lists academic years.
#### `GET /api/v1/academics/terms/` — Lists academic terms/semesters.
#### `GET /api/v1/academics/departments/` — Lists departments.
#### `GET /api/v1/academics/courses/` — Lists academic programs/degrees.
#### `GET /api/v1/academics/subjects/` — Lists course subjects.
#### `GET /api/v1/academics/classes/` — Lists class cohorts and enrolled sections.
#### `GET /api/v1/academics/sections/` — Lists class divisions/sections.

---

### 6.7 Attendance Tracking

#### `GET /api/v1/attendance/records/`
Retrieves daily attendance records.
- **Query Params:** `date` (`YYYY-MM-DD`), `section` (UUID), `status` (`present`, `absent`, `late`, `excused`)

#### `POST /api/v1/attendance/records/bulk-mark/`
Bulk marks daily attendance for an entire classroom section.
- **Request Body:**
```json
{
  "section_id": "2db91038-279e-491a-b448-c1febadaa944",
  "date": "2026-09-18",
  "entries": [
    {
      "student_id": "d4fc7b11-8d29-4842-835f-4d17199e35ab",
      "status": "present",
      "remarks": ""
    },
    {
      "student_id": "5c563e60-084c-41d0-b5c5-3cf1ddcb0a78",
      "status": "absent",
      "remarks": "Medical leave reported"
    }
  ]
}
```
- **Response (`200 OK`):**
```json
{
  "success": true,
  "message": "Successfully marked attendance for 2 students.",
  "data": { "count": 2 }
}
```

#### `GET /api/v1/attendance/corrections/`
Lists attendance correction requests from students/educators.

---

### 6.8 Examinations & Grading

#### `GET /api/v1/exams/exams/`
Lists institutional examinations.

#### `POST /api/v1/exams/exams/{id}/publish/`
Publishes exam results to student and guardian portals, locking marks.

#### `GET /api/v1/exams/marks/`
Lists marks obtained across exam subjects.
- **Query Params:** `exam` (UUID), `student` (UUID)

#### `PATCH /api/v1/exams/marks/{id}/`
Updates mark score for a learner.
- **Request Body:**
```json
{
  "marks_obtained": "92.50"
}
```

---

### 6.9 Finance, Invoicing & Payments

#### `GET /api/v1/finance/invoices/`
Lists student fee invoices.
- **Filters:** `student` (UUID), `status` (`issued`, `partially_paid`, `paid`)

#### `POST /api/v1/finance/invoices/generate/`
Generates a new fee invoice from institutional fee structures.

#### `POST /api/v1/finance/payments/record/`
Records an idempotent payment transaction against an outstanding invoice.
- **Request Body:**
```json
{
  "invoice_id": "b17956dd-a31a-4a63-9726-dc0d6f56541e",
  "amount": "1500.00",
  "payment_method": "card",
  "transaction_reference": "TXN-CARD-4421"
}
```
- **Response (`201 Created`):**
```json
{
  "success": true,
  "message": "Payment recorded successfully. Receipt: RCP-2026-003.",
  "data": {
    "id": "d5b91be1-4f43-41cc-ae09-c933111c2ef6",
    "receipt_number": "RCP-2026-003",
    "amount": "1500.00",
    "payment_method": "card",
    "status": "success",
    "payment_date": "2026-09-18T18:30:00Z"
  }
}
```

---

### 6.10 Communications & Bulletins

#### `GET /api/v1/communications/announcements/`
Lists campus bulletins and announcements.

#### `POST /api/v1/communications/announcements/`
Publishes an institutional announcement.
- **Request Body:**
```json
{
  "title": "Semester Registration Deadline Extended",
  "content": "Course add/drop period is extended until Friday, October 2nd.",
  "target_audience": "all",
  "is_published": true
}
```

#### `GET /api/v1/communications/notifications/`
Lists in-app notifications for authenticated user.

#### `POST /api/v1/communications/notifications/{id}/mark-read/`
Marks notification as read.

---

### 6.11 Audit Logging

#### `GET /api/v1/audit/`
Immutable audit log viewer (Restricted to Institution Admins & Auditors).
- **Filters:** `resource_type` (`Student`, `Invoice`, `AttendanceRecord`), `action` (`CREATE`, `UPDATE`, `DELETE`)
- **Fields:** `id`, `actor_email`, `action`, `resource_type`, `resource_id`, `description`, `ip_address`, `timestamp`.

---

## 7. Demo Accounts for Testing

| Role | Email | Password | Tenant |
|---|---|---|---|
| **Institution Admin** | `eleanor.vance@omni-edu.org` | `Password123!` | Oxford Crest University (`oxford-crest`) |
| **Faculty Member** | `arthur.pendelton@omni-edu.org` | `Password123!` | Oxford Crest University (`oxford-crest`) |
| **Student** | `devan.nair@omni-edu.org` | `Student123!` | Oxford Crest University (`oxford-crest`) |
