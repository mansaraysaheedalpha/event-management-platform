-- Add email backup code fields for 2FA recovery
-- When user loses access to authenticator app, they can receive a code via email

ALTER TABLE "users" ADD COLUMN "emailBackupCode" TEXT;
ALTER TABLE "users" ADD COLUMN "emailBackupCodeExpiresAt" TIMESTAMP(3);
