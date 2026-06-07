# KaamWala AI — Architecture

> This document describes the current backend architecture as implemented.
> Planned or future components are not included here; see ROADMAP.md.

---

## Overview

The backend is a single FastAPI application backed by a PostgreSQL database.
It is designed as a **layered service architecture** — each layer has a single
responsibility and may only call the layer below it.

```
HTTP Request
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  API Layer  (app/api/)                              │
│  Thin route handlers. Validate input via schemas,   │
│  inject dependencies, delegate to the service layer.│
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  Service Layer  (app/services/)                     │
│  All business logic, ownership checks, state        │
│  machine enforcement, and DB writes live here.      │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  Data Layer  (app/models/ + app/db/)                │
│  SQLAlchemy ORM models and async session management.│
└─────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Concern | Choice |
|---------|--------|
| Web framework | FastAPI (ASGI) |
| Database | PostgreSQL (asyncpg driver) |
| ORM | SQLAlchemy 2.0 — async, mapped columns, typed relationships |
| Validation | Pydantic v2 |
| Authentication | JWT (python-jose, HS256), phone-based OTP |
| Settings | pydantic-settings reading from `.env` |
| Server | uvicorn |

---

## Directory Structure

```
backend/
├── app/
│   ├── api/                  # Route handlers (thin adapters)
│   │   ├── auth.py
│   │   ├── health.py
│   │   ├── provider_listings.py
│   │   └── job_requests.py   # Also hosts /{job_id}/interest[s] routes
│   ├── core/                 # Cross-cutting infrastructure
│   │   ├── config.py         # pydantic-settings singleton
│   │   ├── security.py       # JWT create / verify / extract
│   │   └── dependencies.py   # FastAPI Depends — CurrentUser, DBSession
│   ├── db/
│   │   ├── base.py           # DeclarativeBase (no model imports)
│   │   ├── session.py        # Async engine + session factory + get_db
│   │   └── init_db.py        # create_tables() — dev only
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── provider_listing.py
│   │   ├── job_request.py
│   │   └── job_interest.py   # Phase 2B — provider interest bridge table
│   ├── schemas/              # Pydantic request / response schemas
│   │   ├── user.py
│   │   ├── provider_listing.py
│   │   ├── job_request.py
│   │   └── job_interest.py   # Phase 2B — JobInterestCreate / Response
│   ├── services/             # Business logic layer
│   │   ├── auth_service.py
│   │   ├── provider_listing_service.py
│   │   ├── job_request_service.py
│   │   └── job_interest_service.py  # Phase 2B — express / list / withdraw
│   ├── utils/
│   │   └── otp.py            # OTP generate / store / verify (in-memory stub)
│   └── main.py               # App factory, middleware, router registration
├── .env.example
├── requirements.txt
└── README.md
```

---

## API Layer (`app/api/`)

Route handlers are intentionally minimal. Each handler:

1. Receives the request body via a Pydantic schema (validation is automatic).
2. Receives injected dependencies (`DBSession`, `CurrentUser`) via `Depends`.
3. Calls exactly one service function.
4. Returns the service result.

No business logic, no direct ORM queries, no raw SQL.

### Router registration (`main.py`)

```
/                              → health.router              (no prefix)
/api/v1/auth/*                 → auth.router
/api/v1/provider-listings/*    → provider_listings.router
/api/v1/job-requests/*         → job_requests.router
  including: /{job_id}/interest[s]  (Phase 2B interest sub-routes)
```

### Route ordering

In both `provider_listings.py` and `job_requests.py`, the `/me` route is
registered **before** the `/{id}` parameterised route. FastAPI matches routes
in declaration order; without this, the literal string `"me"` would be
interpreted as a UUID path parameter and cause a 422 validation error.

---

## Core Layer (`app/core/`)

### `config.py`

A `pydantic-settings` `Settings` object reads from `.env` (or environment
variables) and is exposed as a module-level singleton via `@lru_cache`. All
other modules import `settings` directly from this module.

### `security.py`

Three pure functions with no side effects:

- `create_access_token(subject, extra_data)` — builds and signs a JWT.
- `verify_token(token)` — decodes and validates; raises `JWTError` on failure.
- `extract_user_id(token)` — verifies and extracts the `sub` claim.

### `dependencies.py`

Defines two `Annotated` type aliases used in route signatures:

- `DBSession = Annotated[AsyncSession, Depends(get_db)]`
- `CurrentUser = Annotated[User, Depends(get_current_user)]`

`get_current_user` resolves a Bearer token → user UUID → DB lookup → active
check. It returns `401` for all authentication failures (including a valid
token for a deleted user, to avoid confirming user existence) and `403` for
deactivated accounts.

---

## Service Layer (`app/services/`)

### `auth_service.py`

| Function | Responsibility |
|----------|----------------|
| `get_user_by_phone` | CRUD: SELECT by phone |
| `get_user_by_id` | CRUD: SELECT by UUID |
| `register_user` | Create user if new, generate + dispatch OTP |
| `verify_otp_and_login` | Validate OTP, flip `is_phone_verified`, issue JWT |

The `/register` endpoint acts as both registration and login — a verified user
who calls it receives a fresh OTP, which they verify to get a new token.

### `provider_listing_service.py`

| Function | Responsibility |
|----------|----------------|
| `get_listing_by_id` | CRUD: SELECT by UUID |
| `get_listings_by_user_id` | CRUD: SELECT all for a user |
| `create_listing` | Guard phone verification, create, compute completion % |
| `list_listings` | Paginated browse with optional `service_category` + `city` filters |
| `get_listing_detail` | Fetch by ID, increment `views_count` |
| `get_my_listings` | Return all listings for the authenticated user |
| `update_listing` | Ownership check, PATCH apply, recompute completion % |

`_compute_profile_completion` scores 8 fields and returns an integer 0–100.

### `job_request_service.py`

| Function | Responsibility |
|----------|----------------|
| `create_job` | Guard phone verification, create |
| `get_my_jobs` | Return all jobs for the authenticated user |
| `get_job_by_id` | Fetch by ID, increment `views_count` |
| `browse_jobs` | Paginated browse — open jobs only — with optional filters |
| `update_job` | Ownership + terminal-state check, PATCH apply |
| `close_job` | Ownership + terminal-state check, set status to `cancelled` |

### `job_interest_service.py` (Phase 2B)

| Function | Responsibility |
|----------|----------------|
| `express_interest` | Guard phone verification + listing ownership + open-job check + duplicate check, create interest |
| `list_interests` | Job-ownership check, return all interests with embedded provider summary |
| `withdraw_interest` | Listing-ownership check, delete interest record |

`_TERMINAL_STATUSES = {cancelled, completed}` guards both `update_job` and
`close_job`. Attempts to modify a terminal job return `409 Conflict`.

> **Note:** `completed` is included in the terminal set for forward compatibility,
> but no service function currently transitions a job to `completed`. The only
> way a job exits `open` today is via `close_job`, which sets `cancelled`.
> Full lifecycle transitions (`assigned`, `completed`) are implemented in Phase 2C.

---

## Models (`app/models/`)

All models inherit from `Base` (`app/db/base.py`). All primary keys are UUIDs.
All timestamps use timezone-aware `TIMESTAMPTZ`.

### Circular import avoidance

Each model file uses two techniques:

1. `from __future__ import annotations` — defers all annotation evaluation,
   preventing SQLAlchemy from trying to resolve forward-reference strings at
   import time.
2. `TYPE_CHECKING` guards — cross-model imports (needed only for type hints)
   are inside `if TYPE_CHECKING:` blocks, so they are never executed at runtime.

`Base` in `db/base.py` does **not** import any model. Models are registered
with `Base.metadata` as a side-effect of the transitive import chain
`main.py → api/ → services/ → models/`.

### `User` (`users`)

Central identity record. Fields are grouped by concern:

- **Identity:** `id`, `phone`, `name`, `user_type`
- **Auth state:** `is_phone_verified`, `is_active`
- **Contact-flow (future):** `free_contacts_remaining`, `has_used_pay_later`, `outstanding_debt`, `debt_incurred_at`

Relationships (both `lazy="noload"` — never loaded on auth paths):
- `provider_listings` → `list[ProviderListing]` (one-to-many)
- `job_requests` → `list[JobRequest]` (one-to-many, scoped to `customer_id`)

### `ProviderListing` (`provider_listings`)

Advertises a provider's service. Fields are grouped by concern:

- **Content:** `title`, `description`, `service_category`, `city`, `area`, `starting_price`, `pricing_notes`, `experience_years`
- **Visibility controls:** `phone_visible`, `can_receive_referrals`, `is_verified`, `is_active`
- **System counters (read-only):** `completed_jobs_count`, `referral_count`, `trust_score`, `profile_completion_percentage`, `free_unlock_credits`, `views_count`

Relationship (`lazy="selectin"` — always loaded with the listing):
- `user` → `User` (many-to-one)

### `JobInterest` (`job_interests`) — Phase 2B

Bridge table between a `JobRequest` and a `ProviderListing`.  Fields:

- **Core:** `job_id` (FK CASCADE), `provider_listing_id` (FK CASCADE), `message`, `quoted_price`
- **Unique constraint:** `(job_id, provider_listing_id)` — one interest per listing per job.

Relationships:
- `job` → `JobRequest` (`lazy="noload"`)
- `provider_listing` → `ProviderListing` (`lazy="selectin"` — loads listing + user eagerly for response embedding)

### `JobRequest` (`job_requests`)

Represents a customer's demand for a service. Fields are grouped by concern:

- **Content:** `title`, `description`, `service_category`, `city`, `area`, `budget_min`, `budget_max`, `urgency`, `preferred_visit_date`
- **Lifecycle:** `job_status` — only `open` and `cancelled` have active application
  logic. `assigned` and `completed` are valid PostgreSQL ENUM values and are
  included in `_TERMINAL_STATUSES`, but no code path currently transitions a job
  into either state. Full lifecycle transitions are implemented in Phase 2C.
- **Assignment (future):** `assigned_provider_id` (FK with `ON DELETE SET NULL`)
- **System counters (read-only):** `contact_unlocked_count`, `views_count`
- **Future-phase columns (no logic yet):** `referral_count`, `trust_boost_score`, `is_featured`

Relationship (`lazy="selectin"` — always loaded with the job):
- `customer` → `User` (many-to-one, via `customer_id`)

---

## Schemas (`app/schemas/`)

Pydantic v2 schemas are separated from ORM models. Three categories exist in
each domain module:

| Category | Purpose |
|----------|---------|
| `*Create` | Request body for POST — all required/optional input fields |
| `*Update` | Request body for PUT — all fields optional (PATCH semantics) |
| `*Response` | Response body — all fields the API returns |

Conventions enforced at schema level (not in the service layer):

- Phone normalisation to E.164 via `@field_validator`.
- String stripping and city title-casing via `@field_validator`.
- Budget range coherence (`max >= min`) via `@model_validator(mode="after")`.
- `model_dump(exclude_unset=True)` in update paths applies PATCH semantics.

`from_orm_with_owner` / `from_orm_with_customer` class methods embed nested
summary objects (`ListingOwnerSummary`, `JobCustomerSummary`) and apply
conditional phone masking without polluting the service layer.

---

## Database Layer (`app/db/`)

### Session management (`session.py`)

| Setting | Value | Reason |
|---------|-------|--------|
| `pool_pre_ping=True` | — | Recovers stale idle connections after DB restarts |
| `pool_size=10` | — | Baseline concurrent connections |
| `max_overflow=20` | — | Burst capacity; total cap = 30 |
| `expire_on_commit=False` | — | ORM objects usable after commit without an extra SELECT |
| `autoflush=False` | — | Service layer controls flush timing explicitly |

`get_db()` yields one session per HTTP request, commits on clean exit,
rolls back on exception, and always closes the connection in `finally`.

### Table creation (`init_db.py`)

`create_tables(engine)` calls `Base.metadata.create_all()` and is invoked by
the startup hook in `main.py`. This is a **dev-only convenience** — in
production, Alembic migrations must be used.

---

## PostgreSQL Relationships Summary

```
users
 ├─ id ──────────────────────────────────────────────────────────────────┐
 │                                                                        │
 │  provider_listings                                                     │
 │   └── user_id → users.id  (ON DELETE CASCADE)                         │
 │        └── id ─────────────────────────────────────────────────────┐  │
 │                                                                     │  │
 │  job_requests                                                       │  │
 │   ├── customer_id → users.id  (ON DELETE CASCADE)  ────────────────┼──┘
 │   ├── assigned_provider_id → users.id  (ON DELETE SET NULL)        │
 │   └── id ───────────────────────────────────────────────────────┐  │
 │                                                                  │  │
 │  job_interests  (Phase 2B)                                       │  │
 │   ├── job_id → job_requests.id  (ON DELETE CASCADE)  ───────────┘  │
 │   └── provider_listing_id → provider_listings.id  (ON DELETE CASCADE)┘
 │        UNIQUE (job_id, provider_listing_id)
```

- **CASCADE on `provider_listings.user_id`** — deleting a user removes all their listings.
- **CASCADE on `job_requests.customer_id`** — deleting a customer removes all their jobs.
- **SET NULL on `job_requests.assigned_provider_id`** — deleting a provider user nullifies the assignment without deleting the job record.
- **CASCADE on `job_interests.job_id`** — deleting a job removes all its interest records.
- **CASCADE on `job_interests.provider_listing_id`** — deleting a listing removes all its interest records.

---

## Authentication Flow (sequence)

```
Client                      API                     Service            DB
  │                          │                          │               │
  │── POST /auth/register ──▶│                          │               │
  │   {phone, name}          │── register_user() ──────▶│               │
  │                          │                          │── SELECT ────▶│
  │                          │                          │◀─ user/None ──│
  │                          │                          │               │
  │                          │                (create if new)           │
  │                          │                          │── INSERT ────▶│
  │                          │                          │               │
  │                          │                (generate + log OTP)      │
  │◀─ {message, detail} ────│                          │               │
  │                          │                          │               │
  │── POST /auth/verify-otp ▶│                          │               │
  │   {phone, otp}           │── verify_otp_and_login()▶│               │
  │                          │                          │ verify OTP    │
  │                          │                          │── SELECT ────▶│
  │                          │                          │◀─ user ───────│
  │                          │                          │ set verified  │
  │                          │                          │── UPDATE ────▶│
  │◀─ {access_token, user} ─│                          │               │
```

---

## CORS

Currently configured with `allow_origins=["*"]`.
This must be restricted to the frontend's origin(s) before any production deployment.
