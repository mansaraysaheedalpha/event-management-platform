-- AlterTable
ALTER TABLE "User" ADD COLUMN     "preferredLanguage" TEXT DEFAULT 'en',
ADD COLUMN     "sponsorId" TEXT,
ADD COLUMN     "tier" TEXT DEFAULT 'default';
