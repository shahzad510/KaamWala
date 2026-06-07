# KaamWala AI — Roadmap

> This document tracks what has been built, what is next, and the longer-term
> product vision. Items are labelled with their implementation status.
>
> **Status legend**
> - ✅ Implemented
> - 🔜 Next up (defined, not started)
> - 💡 Planned (intent clear, design TBD)
> - 🌱 Future idea (vision-level, not designed)

---

## Implemented (as of June 2026)

| Phase | Feature |
|-------|---------|
| MVP   | Phone-OTP authentication, JWT, User model |
| 1A    | Provider Listings — create, browse, update, profile completion % |
| 2A    | Job Requests — post, browse (open only), update, cancel |

See [PROJECT_STATUS.md](./PROJECT_STATUS.md) for full endpoint and schema details.

---

## Phase 2B — Provider Interest System ✅

**Goal:** Allow providers to express interest in an open job so customers can see who is available before committing to a contact unlock.

### Proposed work
- New model: `JobInterest` — (`job_id`, `provider_id`, `message`, `quoted_price`, `created_at`)
- Endpoints:
  - `POST /job-requests/{job_id}/interest` — provider expresses interest
  - `GET /job-requests/{job_id}/interests` — customer sees list of interested providers (auth, owner only)
  - `DELETE /job-requests/{job_id}/interest` — provider withdraws interest
- Business rules:
  - Only verified providers can express interest.
  - Interest is only allowed on `open` jobs.
  - A provider cannot express interest twice on the same job.
  - Customer sees provider's name and listing profile; phone remains gated behind the contact-unlock flow.

---

## Phase 2C — Job Lifecycle 🔜

**Goal:** Complete the `JobRequest` state machine. `assigned` and `completed` already exist in the PostgreSQL ENUM and in `_TERMINAL_STATUSES` but have no transition logic yet. This phase activates them and adds expiration mechanics for stale jobs.

### New schema columns (to be added via migration)

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `completed_provider_id` | UUID (FK → `users.id` SET NULL) | Yes | The provider who actually completed the job (may differ from `assigned_provider_id` if reassignment occurs) |
| `completed_at` | TIMESTAMPTZ | Yes | Timestamp when the job transitioned to `completed` |
| `last_activity_at` | TIMESTAMPTZ | Yes | Updated on every meaningful state change; drives stale-job detection |

### New `job_status` value (requires ENUM migration)

| Value | Meaning |
|-------|---------|
| `expired` | Job was open for too long with no provider assignment; automatically closed by a background task |

Full status set after Phase 2C: `open` → `assigned` → `completed`; or `open`/`assigned` → `cancelled`; or `open` → `expired`.

### Proposed endpoints

- `POST /job-requests/{job_id}/assign` — customer picks a provider from the interest list (Phase 2B); sets `job_status = assigned`, writes `assigned_provider_id`, and stamps `last_activity_at`.
- `POST /job-requests/{job_id}/complete` — customer confirms job is done; sets `job_status = completed`, writes `completed_provider_id` and `completed_at`, stamps `last_activity_at`.

### Stale-job expiration

- A background task (scheduled job or Celery beat) scans for `open` jobs where `last_activity_at` (or `created_at` as fallback) exceeds a configurable inactivity threshold (e.g. 30 days).
- Eligible jobs are transitioned to `expired` and removed from the public browse feed.
- The customer receives a notification (future: push/SMS) so they can re-post if still needed.

### Impact on provider trust and ratings

- On transition to `completed`, `completed_jobs_count` is incremented on the assigned provider's listing (`provider_listings.completed_jobs_count`).
- `completed_jobs_count` feeds directly into the Trust Score formula (Phase 5).
- Completed jobs unlock the ability for both parties to leave a review (Phase 3). A job must reach `completed` status before the `POST /job-requests/{job_id}/reviews` endpoint becomes available.
- `expired` jobs do not count toward any provider counter and cannot receive reviews.

### Implementation notes

- `_TERMINAL_STATUSES` in `job_request_service.py` already includes `completed`; adding the `complete_job` service function is the only required service-layer change for that transition.
- The `assigned_provider_id` FK (`ON DELETE SET NULL`) is already in place; `completed_provider_id` will use the same pattern.
- `last_activity_at` should be stamped by every service function that changes `job_status`.

---

## Phase 3 — Ratings & Reviews 💡

**Goal:** Build trust through verified post-job ratings from both sides of the transaction.

### Proposed work
- New model: `Review` — (`job_id`, `reviewer_id`, `reviewee_id`, `rating` (1–5), `comment`, `reviewer_type`, `created_at`)
- Reviews are only possible after a job reaches `completed` status.
- Each party (customer, provider) can leave exactly one review per job.
- A provider's average rating is computed and stored on `ProviderListing` (new column: `average_rating`).
- Endpoints:
  - `POST /job-requests/{job_id}/reviews` — submit a review
  - `GET /provider-listings/{id}/reviews` — paginated listing reviews
  - `GET /users/{id}/reviews` — paginated user reviews
- No fake reviews: `reviewer_id` and `reviewee_id` are validated against the job's `customer_id` and `assigned_provider_id`.

---

## Phase 4 — Contact Unlock System 💡

**Goal:** Monetise the platform by gating access to a customer's phone number behind a credit or payment.

### Context (schema already prepared)
The following columns exist but have no active business logic yet:

| Column | Table | Purpose |
|--------|-------|---------|
| `free_contacts_remaining` | `users` | 3 free unlocks per user |
| `has_used_pay_later` | `users` | One-time pay-later privilege |
| `outstanding_debt` | `users` | Unpaid balance in PKR paisa |
| `debt_incurred_at` | `users` | When debt was last charged |
| `free_unlock_credits` | `provider_listings` | Credits from referrals/promotions |
| `contact_unlocked_count` | `job_requests` | How many providers have unlocked a job |
| `phone_visible` | `provider_listings` | Provider controls their own visibility |

### Proposed flow
1. Provider browses open jobs.
2. Provider requests contact unlock for a job.
3. System checks: does the provider have `free_unlock_credits > 0`? → deduct and reveal. Does the user have `free_contacts_remaining > 0`? → deduct and reveal. Otherwise → charge upfront or create debt (if `has_used_pay_later = false`).
4. A new `ContactUnlock` record is written; `contact_unlocked_count` is incremented on the job.
5. Provider receives the customer's phone number in the response.

### Proposed models/endpoints
- New model: `ContactUnlock` — (`job_id`, `provider_id`, `unlocked_at`, `charge_type`)
- `POST /job-requests/{job_id}/unlock` — request contact unlock
- `GET /job-requests/{job_id}/unlock-status` — check if caller has already unlocked

---

## Phase 5 — Trust Score 💡

**Goal:** Compute a reputation score (0–100) for each provider listing, visible to customers browsing the platform.

### Context (schema already prepared)
`trust_score` column exists on `provider_listings` (default 0, not yet computed).

### Proposed scoring inputs
| Signal | Weight (indicative) |
|--------|---------------------|
| `profile_completion_percentage` | Low |
| `average_rating` (from Phase 3) | High |
| `completed_jobs_count` | Medium |
| `is_verified` (admin badge) | Medium |
| `referral_count` | Low |
| Account age | Low |

- Score is recomputed asynchronously (background task or scheduled job) after each event that changes an input signal.
- Verified listings receive a trust floor (minimum score regardless of other signals).
- Trust score feeds into browse ranking order in a future phase.

---

## Phase 6 — Referrals 💡

**Goal:** Grow supply-side (provider) acquisition through a referral incentive programme.

### Context (schema already prepared)
| Column | Table | Purpose |
|--------|-------|---------|
| `referral_count` | `provider_listings` | How many referrals the listing has received |
| `referral_count` | `job_requests` | How many referrals a job has received (future) |
| `can_receive_referrals` | `provider_listings` | Provider opt-out flag |
| `free_unlock_credits` | `provider_listings` | Reward for referrals |

### Proposed work
- New model: `Referral` — (`referrer_id`, `referee_id`, `listing_id`, `reward_type`, `created_at`)
- A referrer shares a unique link; when a new provider registers and creates a listing via that link, the referrer earns `free_unlock_credits`.
- Referral chain depth: limit to one level to prevent pyramid structures.
- `can_receive_referrals = false` on a listing hides it from referral surfaces.

---

## Phase 7 — Subscriptions 💡

**Goal:** Offer providers a monthly subscription for premium visibility and unlimited contacts.

### Proposed work
- New model: `Subscription` — (`user_id`, `plan_type`, `status`, `started_at`, `expires_at`, `price_paid`)
- Plan types: `basic` (increased contact credits), `premium` (unlimited contacts + featured placement + trust boost).
- Subscription status: `active`, `expired`, `cancelled`.
- Active subscription suppresses per-contact charges.
- Endpoints:
  - `POST /subscriptions` — subscribe to a plan
  - `GET /subscriptions/me` — return current subscription state
  - `POST /subscriptions/cancel` — cancel at period end

---

## Phase 8 — Payments 💡

**Goal:** Integrate a payment gateway to handle contact-unlock charges, debt collection, and subscription billing.

### Proposed work
- Integrate a Pakistani payment gateway (e.g. JazzCash, EasyPaisa, or Stripe with PKR support).
- New model: `Payment` — (`user_id`, `amount_paisa`, `payment_type`, `status`, `gateway_reference`, `created_at`)
- Payment types: `contact_unlock`, `debt_repayment`, `subscription`.
- Webhook endpoint to receive payment confirmation from the gateway.
- On confirmed payment: update `outstanding_debt`, activate subscription, or issue `free_unlock_credits`.
- `outstanding_debt` on `User` and `debt_incurred_at` are already in the schema for the debt collection path.

---

## Future Ecosystem Ideas 🌱

These are directional ideas without a committed design. They are listed to
capture product intent for future planning sessions.

### KaamWala Mobile App
- React Native or Flutter app consuming the existing API.
- Push notifications (OTP, job interest alerts, contact unlocks).
- Provider location sharing during active job.

### KaamWala Maps Integration
- Geospatial columns (`lat`, `lng`) on `provider_listings` and `job_requests`.
- Proximity-based search (find providers within X km).
- PostgreSQL `PostGIS` extension or a dedicated geosearch service.

### Admin Panel
- Web dashboard for operations team.
- Manage `is_verified` on listings.
- View and resolve `outstanding_debt` cases.
- Moderate reported listings and users.
- Platform-wide analytics (active providers, jobs posted per day, revenue).

### AI Matching
- Recommend the top N providers for a job based on category, city, trust score, and historical job completion rate.
- Notify matched providers when a new job is posted in their category/city.
- Powered by a lightweight ranking model or a rules-based scoring function as a first step.

### Provider Portfolio
- Allow providers to upload photos of completed work.
- Display a gallery on the listing page.
- Object storage (S3-compatible) for images.

### SMS OTP (Production)
- Replace the in-process OTP stub with a real SMS gateway (Twilio, Vonage, or a local Pakistani carrier).
- Move OTP storage to Redis for multi-process deployments and configurable TTL.

### Alembic Migrations
- Scaffold `alembic/` and `env.py`.
- All future schema changes are delivered as versioned, reversible migration scripts.
- Prerequisite for any production deployment.
