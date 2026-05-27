# KaamWala API — Week 1-2 MVP Backend

FastAPI · PostgreSQL · SQLAlchemy 2.0 async · JWT Auth

---

## Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.111+ |
| Database | PostgreSQL 15+ |
| ORM | SQLAlchemy 2.0 async (asyncpg) |
| Auth | JWT via python-jose |
| Validation | Pydantic v2 |
| Runtime | Python 3.12 |

---

## Project Structure

```
backend/
├── app/
│   ├── api/            # Route handlers (thin, no business logic)
│   │   ├── auth.py
│   │   └── health.py
│   ├── core/           # Config, JWT security, DI dependencies
│   │   ├── config.py
│   │   ├── security.py
│   │   └── dependencies.py
│   ├── db/             # Engine, session factory, table creation
│   │   ├── base.py
│   │   ├── session.py
│   │   └── init_db.py
│   ├── models/         # SQLAlchemy ORM models
│   │   └── user.py
│   ├── schemas/        # Pydantic request/response schemas
│   │   └── user.py
│   ├── services/       # Business logic layer
│   │   └── auth_service.py
│   ├── utils/          # Reusable utilities
│   │   └── otp.py      # OTP stub (replace with SMS gateway in prod)
│   └── main.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## 1. PostgreSQL Setup

```bash
# macOS (Homebrew)
brew install postgresql@15 && brew services start postgresql@15

# Ubuntu / Debian
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql

# Create database and user
psql -U postgres
```

```sql
CREATE DATABASE kaamwala;
CREATE USER kaamwala_user WITH ENCRYPTED PASSWORD 'your_strong_password';
GRANT ALL PRIVILEGES ON DATABASE kaamwala TO kaamwala_user;
\q
```

---

## 2. Python Setup

```bash
# From the backend/ directory
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. Environment Variables

```bash
cp .env.example .env
# Open .env and fill in DATABASE_URL, JWT_SECRET_KEY, etc.
```

Generate a secure JWT secret:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 4. Run the Application

```bash
# Development (auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

API docs available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc:       http://localhost:8000/redoc

---

## 5. API Reference

### Health

```
GET  /health        — liveness check
GET  /health/db     — database connectivity check
```

### Auth

```
POST /api/v1/auth/register     — register phone, receive OTP (logged to terminal in MVP)
POST /api/v1/auth/verify-otp   — verify OTP, receive JWT
GET  /api/v1/auth/me           — get current user (Bearer token required)
```

---

## 6. Test with curl

### Register

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"phone": "03001234567", "name": "Ali Raza"}' | python3 -m json.tool
```

Expected response:
```json
{
  "message": "OTP sent successfully",
  "detail": "OTP sent to +923001234567"
}
```

Check the terminal logs for the OTP (e.g. `OTP: 4821`).

---

### Verify OTP

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"phone": "03001234567", "otp": "4821"}' | python3 -m json.tool
```

Expected response:
```json
{
  "access_token": "<jwt_token>",
  "token_type": "bearer",
  "user": {
    "id": "...",
    "phone": "+923001234567",
    "name": "Ali Raza",
    "user_type": "customer",
    "is_phone_verified": true,
    "free_contacts_remaining": 3,
    "is_active": true,
    "created_at": "2026-05-26T..."
  }
}
```

---

### Protected /me route

```bash
TOKEN="<paste access_token here>"

curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## 7. Notes for Production

- Replace OTP stub in `app/utils/otp.py` with Twilio / any SMS gateway.
- Replace the in-memory OTP store with Redis (per-key TTL).
- Run Alembic migrations instead of `create_tables()` at startup.
- Set `DEBUG=false` and restrict `CORS` origins.
- Use a reverse proxy (nginx / Caddy) in front of uvicorn.

---

## 8. Git Commit Message (Phase 1)

```
feat(backend): scaffold Week 1-2 MVP auth foundation

- FastAPI app with async SQLAlchemy 2.0 + asyncpg
- User model with UUID PK, phone verification, contact-flow fields
- Phone-based registration with 4-digit OTP stub (logs to terminal)
- JWT access token issuance on OTP verification
- /auth/register, /auth/verify-otp, /auth/me endpoints
- Pydantic v2 schemas with Pakistani phone number normalisation
- Health + DB liveness endpoints
- Modular layered architecture (api → service → db)
```
