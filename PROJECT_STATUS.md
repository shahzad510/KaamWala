# KaamWala AI — Project Status

> Last updated: June 2026
> Backend stack: FastAPI · PostgreSQL · async SQLAlchemy 2.0 · Pydantic v2

---

## Completed Phases

| Phase | Name | Status |
|-------|------|--------|
| MVP   | Auth Foundation | ✅ Complete |
| 1A    | Provider Listings | ✅ Complete |
| 2A    | Job Requests | ✅ Complete |
| 2B    | Provider Interest System | ✅ Complete |

---

## Current API Endpoints

All versioned endpoints are mounted under `/api/v1`.

### Health (no auth)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check — returns app name, version, timestamp |
| `GET` | `/health/db` | Readiness check — pings the database |

### Authentication (`/api/v1/auth`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | None | Submit phone number → create account if new → dispatch OTP |
| `POST` | `/auth/verify-otp` | None | Validate OTP → mark phone verified → return JWT |
| `GET`  | `/auth/me` | Bearer | Return the authenticated user's profile |

### Provider Listings (`/api/v1/provider-listings`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/provider-listings` | Bearer | Create a new listing (phone must be verified) |
| `GET`  | `/provider-listings/me` | Bearer | Return all listings owned by the caller, newest first |
| `GET`  | `/provider-listings` | None | Paginated public browse; filters: `service_category`, `city` |
| `GET`  | `/provider-listings/{id}` | None | Single listing detail; increments `views_count` |
| `PUT`  | `/provider-listings/{id}` | Bearer | Update listing fields (owner only, PATCH semantics) |

### Job Requests (`/api/v1/job-requests`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/job-requests` | Bearer | Post a new job (phone must be verified) |
| `GET`  | `/job-requests/me` | Bearer | Return all jobs posted by the caller, newest first |
| `GET`  | `/job-requests` | None | Paginated public browse (open jobs only); filters: `city`, `service_category`, `urgency` |
| `GET`  | `/job-requests/{job_id}` | None | Single job detail; increments `views_count` |
| `PUT`  | `/job-requests/{job_id}` | Bearer | Update job fields (owner only, PATCH semantics, non-terminal only) |
| `POST` | `/job-requests/{job_id}/close` | Bearer | Cancel a job (owner only, non-terminal only) |

### Job Interests (`/api/v1/job-requests/{job_id}/interest[s]`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/job-requests/{job_id}/interest` | Bearer | Provider expresses interest; body: `provider_listing_id`, optional `message` + `quoted_price` |
| `GET`  | `/job-requests/{job_id}/interests` | Bearer | Customer views all interested providers (owner only); phone not included |
| `DELETE` | `/job-requests/{job_id}/interest?listing_id={uuid}` | Bearer | Provider withdraws their listing's interest; returns 204 |

---

## Current Database Tables

### `users`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID | No | PK, auto-generated |
| `phone` | VARCHAR(20) | No | Unique (E.164 format, e.g. `+923001234567`) |
| `name` | VARCHAR(255) | Yes | Optional display name |
| `user_type` | ENUM | No | `customer` / `provider` / `both`; default `customer` |
| `is_phone_verified` | BOOLEAN | No | Flipped to `true` on first successful OTP; gates listing/job creation |
| `free_contacts_remaining` | INTEGER | No | Default 3; decremented on each contact unlock |
| `has_used_pay_later` | BOOLEAN | No | One-time pay-later privilege tracker |
| `outstanding_debt` | BIGINT | No | Unpaid debt in PKR paisa; default 0 |
| `debt_incurred_at` | TIMESTAMPTZ | Yes | Timestamp of most recent debt charge |
| `is_active` | BOOLEAN | No | Soft-delete flag; `false` blocks authentication |
| `created_at` | TIMESTAMPTZ | No | Server default: `now()` |
| `updated_at` | TIMESTAMPTZ | No | Auto-updated on every write |

**Indexes:** `ix_users_phone` (unique), `ix_users_created_at`

---

### `provider_listings`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID | No | PK, auto-generated |
| `user_id` | UUID | No | FK → `users.id` ON DELETE CASCADE |
| `title` | VARCHAR(120) | No | |
| `description` | TEXT | Yes | |
| `service_category` | ENUM | No | See ServiceCategory values below |
| `city` | VARCHAR(100) | No | Stored title-cased |
| `area` | VARCHAR(150) | Yes | Sub-city area |
| `starting_price` | INTEGER | Yes | Indicative price in PKR |
| `pricing_notes` | VARCHAR(255) | Yes | Free-form e.g. "Negotiable" |
| `experience_years` | INTEGER | Yes | |
| `phone_visible` | BOOLEAN | No | If `false`, owner phone is masked in responses |
| `completed_jobs_count` | INTEGER | No | System-managed; default 0 |
| `referral_count` | INTEGER | No | System-managed; default 0 |
| `trust_score` | INTEGER | No | System-managed (0–100); default 0 |
| `profile_completion_percentage` | INTEGER | No | Auto-computed on create/update (0–100) |
| `free_unlock_credits` | INTEGER | No | Credits from referrals/promotions; default 0 |
| `can_receive_referrals` | BOOLEAN | No | Default `true` |
| `is_verified` | BOOLEAN | No | Set by admins; default `false` |
| `is_active` | BOOLEAN | No | Default `true` |
| `views_count` | INTEGER | No | Incremented on every `GET /{id}` |
| `created_at` | TIMESTAMPTZ | No | |
| `updated_at` | TIMESTAMPTZ | No | |

**Indexes:** `ix_provider_listings_service_category`, `ix_provider_listings_city`, `ix_provider_listings_is_active`, `ix_provider_listings_created_at`, btree index on `user_id`

**ServiceCategory values:** `electrician`, `plumber`, `carpenter`, `painter`, `cleaner`, `ac_technician`, `welder`, `mason`, `driver`, `guard`, `gardener`, `cook`, `tailor`, `mechanic`, `other`

---

### `job_requests`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID | No | PK, auto-generated |
| `customer_id` | UUID | No | FK → `users.id` ON DELETE CASCADE |
| `title` | VARCHAR(150) | No | |
| `description` | TEXT | Yes | |
| `service_category` | ENUM | No | Shared with `provider_listings` |
| `city` | VARCHAR(100) | No | Stored title-cased |
| `area` | VARCHAR(150) | Yes | |
| `budget_min` | INTEGER | Yes | PKR; schema validates `max >= min` |
| `budget_max` | INTEGER | Yes | PKR |
| `urgency` | ENUM | No | `low` / `medium` / `high` / `emergency`; default `medium` |
| `job_status` | ENUM | No | `open` / `assigned` / `completed` / `cancelled`; default `open`. **Active logic uses only `open` and `cancelled`** — `assigned` and `completed` are reserved schema values for Phase 2C. |
| `preferred_visit_date` | TIMESTAMPTZ | Yes | Customer's requested visit time |
| `assigned_provider_id` | UUID | Yes | FK → `users.id` ON DELETE SET NULL; populated in future phase |
| `contact_unlocked_count` | INTEGER | No | System-managed; default 0 |
| `views_count` | INTEGER | No | Incremented on every `GET /{job_id}` |
| `referral_count` | INTEGER | No | Future-phase counter; default 0 |
| `trust_boost_score` | INTEGER | No | Future-phase visibility boost; default 0 |
| `is_featured` | BOOLEAN | No | Future-phase featured placement; default `false` |
| `created_at` | TIMESTAMPTZ | No | |
| `updated_at` | TIMESTAMPTZ | No | |

**Indexes:** `ix_job_requests_customer_id`, `ix_job_requests_service_category`, `ix_job_requests_city`, `ix_job_requests_job_status`, `ix_job_requests_urgency`, `ix_job_requests_created_at`, `ix_job_requests_assigned_provider_id`

---

### `job_interests`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID | No | PK, auto-generated |
| `job_id` | UUID | No | FK → `job_requests.id` ON DELETE CASCADE |
| `provider_listing_id` | UUID | No | FK → `provider_listings.id` ON DELETE CASCADE |
| `message` | TEXT | Yes | Optional pitch from the provider (max 1 000 chars enforced at schema level) |
| `quoted_price` | INTEGER | Yes | Provider's indicative price for this job in PKR |
| `created_at` | TIMESTAMPTZ | No | Server default: `now()` |

**Unique constraint:** `uq_job_interests_job_listing` on `(job_id, provider_listing_id)` — one interest per listing per job.

**Indexes:** `ix_job_interests_job_id`, `ix_job_interests_provider_listing_id`, `ix_job_interests_created_at`

---

## Current Business Rules

### Authentication
- Phone numbers are accepted as `03XXXXXXXXX` or `+923XXXXXXXXX` and normalised to E.164 (`+923XXXXXXXXX`) before any DB operation.
- OTP is 4 digits, valid for 5 minutes, stored in-process memory (not Redis). Replaying a used OTP fails.
- The `/register` endpoint doubles as the login endpoint for already-verified users — it always sends a fresh OTP.
- Token expiry: 7 days (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).
- A deactivated user (`is_active = false`) receives `403 Forbidden`, not `401`, to distinguish "account banned" from "please log in again".
- A missing or invalid token receives `401` with a `WWW-Authenticate: Bearer` header (RFC 6750 compliant). The 401 is also returned for a valid token whose user no longer exists, to avoid leaking whether a user ID is registered.

### Provider Listings
- Phone must be verified (`is_phone_verified = true`) before a listing can be created.
- One user may own any number of listings (one-to-many).
- `profile_completion_percentage` (0–100) is recomputed on every create and update using 8 scored fields: `title`, `description`, `service_category`, `city`, `area`, `starting_price`, `pricing_notes`, `experience_years`.
- When `phone_visible = false`, the owner's phone is replaced with `null` in all responses.
- Only the listing owner may update their listing. Non-owners receive `403`.
- System-managed counters (`completed_jobs_count`, `referral_count`, `trust_score`, `views_count`) are never accepted from API input.

### Job Requests
- Phone must be verified before a job can be posted.
- Only the posting customer may update or close their job. Non-owners receive `403`.
- **Active job statuses (current phase):** `open` (default on creation) and `cancelled` (set by the `/close` endpoint). These are the only two statuses reachable through existing application logic.
- **Reserved job statuses (future phases):** `assigned` and `completed` exist in the PostgreSQL ENUM and in `_TERMINAL_STATUSES` but no service function transitions a job into either state yet. They will be activated in Phase 2C.
- Jobs in a terminal state (`cancelled` or `completed`) are immutable — update and close attempts return `409 Conflict`. This guard is already in place so that Phase 2C transitions slot in without changing existing logic.
- The public browse feed (`GET /job-requests`) shows only `open` jobs.
- `budget_max` must be ≥ `budget_min` when both are provided; enforced at schema validation level.
- `assigned_provider_id` uses `ON DELETE SET NULL` so deleting a provider user does not cascade-delete associated job records.

---

### Provider Interest (Phase 2B)
- Phone must be verified before expressing interest.
- The `provider_listing_id` in the request body must belong to the authenticated caller; non-owners receive `403`.
- The listing must be active (`is_active = true`); inactive listings receive `403`.
- A user cannot express interest in their own job request (`job.customer_id == listing.user_id`) — returns `409 Conflict`.
- Interest may only be expressed on `open` jobs; other statuses return `409 Conflict`.
- Duplicate `(job_id, provider_listing_id)` pairs return `409 Conflict` (enforced at both service and database level via unique constraint).
- Only the job's posting customer may call `GET /interests`; all other callers receive `403`.
- `DELETE /interest?listing_id=<uuid>` withdraws the interest unconditionally (no job-status restriction). The job must exist (`404` for bad IDs) and the listing must belong to the caller (`403`).
- Provider phone numbers are **never** returned in interest responses — they remain gated behind the contact-unlock system (Phase 4).

---

## Known Limitations (MVP)

- OTP is stored in process memory — does not survive restarts and does not work in multi-process deployments.
- OTP delivery is stubbed — codes are printed to the terminal log only.
- No Alembic migrations exist yet; tables are created via `create_tables()` at startup.
- No rate limiting on OTP generation or token issuance.
- No admin endpoints exist.
- `assigned_provider_id` column exists but no assignment logic is implemented.
- `job_status` values `assigned` and `completed` exist in the database ENUM but are unreachable by current API calls. No endpoint sets either status.
- No background scheduler exists yet; stale-job expiration is planned for Phase 2C.
