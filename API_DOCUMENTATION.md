# Omni Educational Management API

Implementation reference for the Django REST Framework API in this repository. The endpoint catalog below is derived from `config/urls.py`, each app's `urls.py`, viewsets, serializers, permissions, and tests. It describes the current implementation, not planned product functionality.

## Service URLs

The development server listens on `http://127.0.0.1:8000` by default.

| Resource | URL |
| --- | --- |
| API base | `http://127.0.0.1:8000/api/v1/` |
| OpenAPI schema | `http://127.0.0.1:8000/api/v1/schema/` |
| Swagger UI | `http://127.0.0.1:8000/api/v1/docs/` |
| ReDoc | `http://127.0.0.1:8000/api/v1/redoc/` |
| Django admin | `http://127.0.0.1:8000/admin/` |

`schema.yml` at the repository root is the machine-readable OpenAPI contract. Use the served schema or refresh the checked-in snapshot when the routes or serializers change.

## Conventions

### Authentication

Protected endpoints require an authenticated user. The API accepts either:

```http
Authorization: Bearer <access-token>
```

or the `access_token` HTTP-only cookie. The SimpleJWT access token lifetime defaults to 60 minutes and the refresh token lifetime to 7 days; both are configurable with environment variables.

`POST /auth/login/` accepts the normal SimpleJWT credentials (`email` and `password`) and returns `access`, `refresh`, `user`, `accessible_tenants`, and `active_tenant`. A successful login also sets:

- `access_token`: HTTP-only, `Path=/`, `SameSite=Lax`, max age 3600 seconds.
- `refresh_token`: HTTP-only, `Path=/`, `SameSite=Lax`, max age 604800 seconds.

Cookies are marked `Secure` when `DEBUG` is false. Browser clients must send requests with credentials enabled (for example, `fetch(url, { credentials: "include" })`). `POST /auth/refresh/` accepts `refresh` in the JSON body or reads the `refresh_token` cookie when the body value is absent. Refresh responses set the new access cookie and, when token rotation returns one, the refresh cookie. `POST /auth/logout/` is public and deletes `access_token`, `refresh_token`, and `sessionid`; it does not blacklist a JWT.

`POST /auth/register-institution/` is public and returns tokens in its JSON response, but it does not set authentication cookies.

### Tenant context

Tenant-scoped endpoints resolve context from `X-Tenant-ID`, which may be a tenant UUID or slug:

```http
X-Tenant-ID: 7d18388a-872b-4d2b-b42a-f658c03e9e60
```

If the header is omitted, the middleware selects the authenticated user's active membership, preferring `is_default` and then the most recently joined membership. Supplying a tenant does not bypass membership checks: non-superusers must have an active membership in that tenant. Superusers may select any non-deleted tenant. A missing active tenant generally produces an empty tenant-scoped queryset or a permission failure; `GET /tenants/current/` returns `400 NO_ACTIVE_TENANT`.

`X-Request-ID` is optional. The middleware preserves a supplied value or generates one and returns it on the response. CORS allows both tenant/request headers and credentials for configured origins.

### Response formats

Successful custom responses use the following shape:

```json
{
  "success": true,
  "data": {},
  "meta": {"request_id": "uuid"}
}
```

Some successful DRF serializer responses (for example ordinary create/update/detail operations) are returned directly as serialized objects rather than wrapped. Custom workflow endpoints include `success`, `message`, and `data` as shown in their examples.

All handled errors use this shape:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Input validation failed. Please check the provided fields.",
    "details": {"field": ["This field is required."]}
  },
  "meta": {
    "request_id": "uuid",
    "timestamp": "2026-09-18T18:00:00+00:00"
  }
}
```

Common codes are `AUTHENTICATION_REQUIRED`, `PERMISSION_DENIED`, `CROSS_TENANT_FORBIDDEN`, `VALIDATION_ERROR`, `NOT_FOUND`, `METHOD_NOT_ALLOWED`, `NO_ACTIVE_TENANT`, and `INTERNAL_SERVER_ERROR`. Error status codes are normally `400`, `401`, `403`, `404`, `405`, or `500`; the readiness endpoint additionally returns `503` when its database check fails.

### Pagination, filtering, and ordering

DRF list endpoints use `StandardResultsSetPagination`: `page` defaults to `1`, `page_size` defaults to `25`, and the maximum page size is `100`.

```json
{
  "success": true,
  "data": [],
  "meta": {
    "count": 142,
    "total_pages": 6,
    "current_page": 1,
    "page_size": 25,
    "next": "http://127.0.0.1:8000/api/v1/students/?page=2",
    "previous": null,
    "request_id": "uuid"
  }
}
```

Where documented below, `?field=value` uses `DjangoFilterBackend`, `?search=value` uses `SearchFilter`, and `?ordering=field` uses `OrderingFilter`. UUID values are represented as strings. Dates use `YYYY-MM-DD`; datetimes are ISO 8601.

## Endpoint catalog

Unless stated otherwise, a router resource supports `GET` collection (list), `POST` collection (create), `GET` detail (retrieve), `PUT`/`PATCH` detail (replace/partial update), and `DELETE` detail (destroy). All router detail identifiers are UUIDs. Collection reads are included in the permission notes below.

### Health

| Method and path | Access | Result |
| --- | --- | --- |
| `GET /health/` | Public | Liveness response with `status`, `service`, `version`, and timestamp. |
| `GET /ready/` | Public | Database readiness response; `200` when connected, `503` otherwise. |

### Identity, authentication, and RBAC

| Method and path | Access | Result |
| --- | --- | --- |
| `POST /auth/register-institution/` | Public | Atomically creates a tenant, initial user/admin membership, permissions, audit entry, and returns `user`, `tenant`, and `tokens`. |
| `POST /auth/login/` | Public | Returns JWTs and tenant membership information; also sets auth cookies. |
| `POST /auth/refresh/` | Public token endpoint | Refresh body or cookie; returns a new access token and updates cookies. |
| `POST /auth/logout/` | Public | Deletes auth cookies. |
| `GET /auth/me/` | Authenticated | Returns `user`, `active_tenant`, `active_permissions`, and active `memberships`. |
| `POST /auth/switch-tenant/` | Authenticated | Body `{ "tenant_id": "<uuid-or-slug>" }`; marks the user's active membership as default. |
| `GET /permissions/` | Active tenant member | Lists the permission catalog. |
| `/roles/` | Institution admin | Standard CRUD for tenant roles and system roles. |
| `/memberships/` | Institution admin | Standard CRUD for memberships in the active tenant. |

`GET /auth/me/` and `POST /auth/switch-tenant/` return `401` without credentials. Switching to a tenant without an active membership returns `403 CROSS_TENANT_FORBIDDEN`.

### Tenants

| Resource | Access and filters |
| --- | --- |
| `/tenants/` | `GET` list/retrieve is authenticated and returns the user's active memberships (or all tenants for a superuser). `POST` and `DELETE` require a superuser. `PUT`/`PATCH` require an institution admin. |
| `GET /tenants/current/` | Authenticated; returns the resolved tenant detail or `400` if no tenant is active. |

### Students and admissions

| Resource/action | Access and filters |
| --- | --- |
| `/students/` | `GET` requires `students.view`; create requires `students.create`; update/patch requires `students.update`; delete requires `students.delete`. Filters: `status`, `gender`, `blood_group`; search: `admission_number`, `first_name`, `last_name`; ordering: `admission_number`, `first_name`, `created_at`. Delete is a soft delete. |
| `POST /students/admit/` | Requires `students.create`; runs the admission workflow and returns `201` with `message` and the created student in `data`. |

Admission input supports `first_name`, `last_name`, `date_of_birth`, `gender`, `admission_date`, optional `admission_number`, `email`, `blood_group`, `medical_notes`, `guardian`, enrollment UUIDs (`academic_year_id`, `class_cohort_id`, `section_id`), or enrollment names (`class_name`, `section_name`), and `roll_number`.

```json
{
  "first_name": "Mira",
  "last_name": "Kowalski",
  "date_of_birth": "2006-03-22",
  "gender": "F",
  "admission_date": "2026-09-18",
  "email": "mira.kowalski@example.edu",
  "class_name": "Year 3 Computer Science",
  "section_name": "A"
}
```

### Staff and faculty

| Resource | Access and filters |
| --- | --- |
| `/staff/` | `GET` is authenticated; create/update/patch/delete require `staff.manage`. Filters: `status`, `employment_type`, `department`; search: `employee_id`, user names, `designation`; ordering: `employee_id`, `joined_date`, `created_at`. |

### Academic structure

The following resources all support the standard CRUD methods. `GET` operations require an active tenant member. Create/update/patch/delete require `academics.manage`.

`/academics/years/`, `/academics/terms/`, `/academics/departments/`, `/academics/courses/`, `/academics/subjects/`, `/academics/classes/`, and `/academics/sections/`.

### Attendance

| Method and path | Access | Filters/body |
| --- | --- | --- |
| `/attendance/records/` CRUD | List/retrieve requires `attendance.view`; create requires `attendance.mark`; update/patch/delete use `attendance.view`. | Filters: `section`, `subject`, `student`, `date`, `status`. |
| `POST /attendance/records/bulk-mark/` | `attendance.mark` | `{ "section_id": "uuid", "subject_id": "uuid", "date": "YYYY-MM-DD", "entries": [{"student_id": "uuid", "status": "present", "remarks": ""}] }`; returns `200` with the count. |
| `/attendance/corrections/` CRUD | Active tenant member; approve/reject require `attendance.correct`. | Filters: `status`, `requested_by`. |
| `POST /attendance/corrections/{id}/approve/` | `attendance.correct` | Applies the correction and returns the updated request. |
| `POST /attendance/corrections/{id}/reject/` | `attendance.correct` | Rejects the correction and returns the updated request. |

Attendance statuses are the model's configured choices; validation is enforced by the serializers.

### Examinations and marks

| Resource/action | Access and filters |
| --- | --- |
| `/exams/grade-scales/` | Standard CRUD; active tenant member. |
| `/exams/exams/` | List/retrieve: active tenant member; create/update/patch/delete: `exams.manage`. Filters: `class_cohort`, `academic_year`, `status`, `is_published`. |
| `POST /exams/exams/{id}/publish/` | `marks.publish`; publishes results and returns the exam. |
| `/exams/schedules/` | Exam-subject schedule CRUD; reads require an active tenant member, writes require `exams.manage`. |
| `/exams/marks/` | List/retrieve: active tenant member (students see only their own marks for published exams); create/update/patch: `marks.enter`; delete: `exams.manage`. Filters: `exam_subject`, `student`, `status`. |

Marks cannot be changed for a published exam. A non-absent mark must be supplied and cannot be negative or exceed the subject's maximum.

### Finance

| Resource/action | Access and filters |
| --- | --- |
| `/finance/categories/` | Standard CRUD; requires `fees.view` for all methods. |
| `/finance/structures/` | Standard CRUD; requires `fees.view` for all methods. |
| `/finance/invoices/` | List/retrieve requires `fees.view`; create and `POST /generate/` require `fees.create_invoice`; other writes use `fees.view`. Filters: `student`, `status`. Students see only their own invoices. |
| `POST /finance/invoices/generate/` | Body: `student_id`, `fee_structure_ids`, `due_date`, optional `discount_amount`; returns `201` with the generated invoice. |
| `/finance/payments/` | List/retrieve requires `fees.view`; create and `POST /record/` require `fees.record_payment`; other writes use `fees.view`. Filters: `invoice`, `status`, `payment_method`. |
| `POST /finance/payments/record/` | Body: `invoice_id`, `amount`, optional `payment_method`, `transaction_reference`, and `idempotency_key`; returns `201` with the payment and receipt. |

```json
{
  "invoice_id": "b17956dd-a31a-4a63-9726-dc0d6f56541e",
  "amount": "1500.00",
  "payment_method": "card",
  "transaction_reference": "TXN-CARD-4421",
  "idempotency_key": "checkout-4421"
}
```

### Communications

| Resource/action | Access |
| --- | --- |
| `/communications/announcements/` | List/retrieve requires an active tenant member; create/update/patch/delete require an institution admin. List returns published announcements. |
| `/communications/notifications/` | Read-only list/retrieve for the authenticated recipient. |
| `POST /communications/notifications/{id}/mark-read/` | Authenticated recipient; marks their notification read. |

### Audit

`GET /audit/` requires an institution admin or superuser and returns tenant-scoped immutable audit records. Filters are `action`, `resource_type`, and `actor`; search covers `resource_id`, `description`, `request_id`, and actor email; ordering supports `created_at` (default `-created_at`).

## Local setup

The repository supports SQLite for local development and PostgreSQL when database environment variables are configured.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements\local.txt
Copy-Item .env.example .env
# Set USE_SQLITE_FOR_LOCAL=True in .env for a local SQLite database.
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Create demo data when the command is available:

```powershell
python manage.py seed_demo_data
```

## Curl examples

Register an institution:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register-institution/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.edu","password":"Password123!","first_name":"Ada","last_name":"Lovelace","institution_name":"Example Academy","institution_type":"k12_school","slug":"example-academy"}'
```

Login and capture the JSON access token:

```bash
curl -c cookies.txt -X POST http://127.0.0.1:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.edu","password":"Password123!"}'
```

Call a tenant-scoped endpoint with a bearer token:

```bash
curl http://127.0.0.1:8000/api/v1/students/?page=1\&page_size=25 \
  -H "Authorization: Bearer <access-token>" \
  -H "X-Tenant-ID: <tenant-uuid-or-slug>" \
  -H "X-Request-ID: <client-request-id>"
```

The same request can use the login cookie jar instead:

```bash
curl -b cookies.txt http://127.0.0.1:8000/api/v1/auth/me/
```

## Status code summary

`200` indicates a successful read, update, custom action, health check, or logout; `201` indicates successful creation or workflow creation; `204` is used by DRF deletes when no body is returned; `400` indicates invalid input or missing active tenant; `401` indicates missing/invalid authentication; `403` indicates insufficient permission or cross-tenant access; `404` indicates an unavailable resource in the current tenant; `405` indicates an unsupported method; `503` indicates readiness failure; and `500` indicates an unhandled server error.
