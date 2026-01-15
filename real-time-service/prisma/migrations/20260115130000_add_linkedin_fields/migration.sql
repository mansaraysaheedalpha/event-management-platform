-- Add LinkedIn integration fields to UserReference table
ALTER TABLE "user_references" ADD COLUMN IF NOT EXISTS "linkedInUrl" TEXT;
ALTER TABLE "user_references" ADD COLUMN IF NOT EXISTS "linkedInId" TEXT;
ALTER TABLE "user_references" ADD COLUMN IF NOT EXISTS "linkedInHeadline" TEXT;
ALTER TABLE "user_references" ADD COLUMN IF NOT EXISTS "linkedInAccessToken" TEXT;
ALTER TABLE "user_references" ADD COLUMN IF NOT EXISTS "linkedInRefreshToken" TEXT;
ALTER TABLE "user_references" ADD COLUMN IF NOT EXISTS "linkedInTokenExpiresAt" TIMESTAMP(3);
