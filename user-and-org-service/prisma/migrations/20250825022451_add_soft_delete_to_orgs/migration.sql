-- CreateEnum
CREATE TYPE "public"."OrganizationStatus" AS ENUM ('ACTIVE', 'PENDING_DELETION');

-- AlterTable
ALTER TABLE "public"."Organization" ADD COLUMN     "deletionScheduledAt" TIMESTAMP(3),
ADD COLUMN     "status" "public"."OrganizationStatus" NOT NULL DEFAULT 'ACTIVE';
