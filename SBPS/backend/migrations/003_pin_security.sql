-- 003_pin_security.sql
-- Add columns used for secure PIN verification and lockout.

ALTER TABLE users
ADD COLUMN IF NOT EXISTS pin_hash VARCHAR(255);

ALTER TABLE users
ADD COLUMN IF NOT EXISTS failed_pin_attempts INTEGER NOT NULL DEFAULT 0;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_users_locked_until
ON users(locked_until);
