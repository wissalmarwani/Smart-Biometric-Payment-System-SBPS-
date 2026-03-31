# SBPS Backend (PostgreSQL)

## Project Structure
```
backend/
	app.py                       # Flask entrypoint + static frontend serving
	application_factory.py       # Dependency wiring (Factory pattern)
	ai/                          # AI domain modules
		face_recognition.py        # Embedding utilities
		face_verification.py       # Face comparison strategy + service
		anti_spoofing.py           # Liveness strategies + facade
	services/
		user_service.py            # Core user and transaction service
	security/
		pin_verification_store.py  # PIN verification TTL state
	workflows/
		payment_workflow.py        # PIN + payment orchestration (Facade)
	api/
		http.py                    # Shared API response and decode helpers
		routes.py                  # Blueprint composition only
		endpoints/
			users.py                 # /health, /users, /transactions
			verification.py          # /verify_face, /verify_pin
			payments.py              # /pay
```

## Architecture Notes
- HTTP handlers are split by feature under `api/endpoints`.
- `api/routes.py` only assembles endpoint modules into one blueprint.
- AI code is grouped under `ai/` for recognition and liveness concerns.
- Business/persistence code is grouped under `services/`.
- Security support stores are grouped under `security/`.
- Business orchestration is in `workflows/payment_workflow.py`.
- Data access and transactional logic stay in `services/user_service.py`.

## Init DB
1. Create role and database:
```powershell
psql -U postgres -c "CREATE USER sbps_user WITH PASSWORD 'YOUR_PASSWORD';"
psql -U postgres -c "CREATE DATABASE sbps_db OWNER sbps_user;"
```

2. Apply migrations:
```powershell
psql -U sbps_user -d sbps_db -f "backend/migrations/001_init.sql"
psql -U sbps_user -d sbps_db -f "backend/migrations/002_schema_evolution.sql"
psql -U sbps_user -d sbps_db -f "backend/migrations/003_pin_security.sql"
```

3. Import legacy users backup (one-time):
```powershell
.venv\Scripts\python.exe backend/migrations/migrate_users_json.py
```

4. Hash existing plaintext PINs (recommended):
```powershell
.venv\Scripts\python.exe backend/migrations/hash_existing_pins.py
```

## Run Local
1. Configure environment in `backend/.env`:
```env
DATABASE_URL=postgresql://sbps_user:YOUR_PASSWORD@localhost:5432/sbps_db
DB_POOL_MIN=1
DB_POOL_MAX=20
MAX_PIN_ATTEMPTS=5
PIN_LOCK_SECONDS=300
LIVENESS_ENABLED=true
LIVENESS_STRATEGY=deepface
LIVENESS_MIN_SCORE=0.75
# Use these only for TensorFlow strategy:
# LIVENESS_STRATEGY=tensorflow
# LIVENESS_MODEL_PATH=backend/models/liveness/liveness_model.keras
# LIVENESS_INPUT_SIZE=224
# LIVENESS_LIVE_CLASS_INDEX=1
```

2. Start backend:
```powershell
.venv\Scripts\python.exe backend/app.py
```

## Notes
- Runtime now uses PostgreSQL only.
- `backend/models/users.json` is legacy backup source for migration, not runtime storage.
- For `LIVENESS_STRATEGY=deepface`, install PyTorch (`torch`) in the active virtual environment.
