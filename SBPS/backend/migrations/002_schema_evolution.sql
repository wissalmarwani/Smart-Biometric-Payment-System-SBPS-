-- 002_schema_evolution.sql
-- Evolution migration after initial PostgreSQL cutover.

ALTER TABLE users
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE OR REPLACE FUNCTION set_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_users_updated_at();

ALTER TABLE transactions
ADD COLUMN IF NOT EXISTS reference VARCHAR(64);

CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_reference_unique
ON transactions(reference)
WHERE reference IS NOT NULL;
