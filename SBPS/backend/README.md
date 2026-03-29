# SBPS Backend (PostgreSQL)

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
```

2. Start backend:
```powershell
.venv\Scripts\python.exe backend/app.py
```

3. Optional smoke test (new terminal):
```powershell
Set-Location backend
.\smoke_test.ps1
```

## Notes
- Runtime now uses PostgreSQL only.
- `backend/models/users.json` is legacy backup source for migration, not runtime storage.
