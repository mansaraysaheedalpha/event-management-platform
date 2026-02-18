-- AlterEnum
ALTER TYPE "UserType" ADD VALUE 'VENUE_OWNER';

-- AlterTable
ALTER TABLE "Organization" ADD COLUMN "canCreateEvents" BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE "Organization" ADD COLUMN "canListVenues" BOOLEAN NOT NULL DEFAULT true;
