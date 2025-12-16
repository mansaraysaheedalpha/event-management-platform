-- CreateEnum
CREATE TYPE "UserType" AS ENUM ('ORGANIZER', 'ATTENDEE');

-- AlterTable
ALTER TABLE "User" ADD COLUMN     "userType" "UserType" NOT NULL DEFAULT 'ORGANIZER';
