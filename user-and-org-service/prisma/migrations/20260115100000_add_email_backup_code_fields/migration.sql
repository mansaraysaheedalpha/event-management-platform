-- Add email backup code fields for 2FA recovery
-- When user loses access to authenticator app, they can receive a code via email

ALTER TABLE "User" ADD COLUMN "emailBackupCode" TEXT;
ALTER TABLE "User" ADD COLUMN "emailBackupCodeExpiresAt" TIMESTAMP(3);
