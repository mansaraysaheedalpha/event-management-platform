/*
  Warnings:

  - A unique constraint covering the columns `[emailChangeToken]` on the table `User` will be added. If there are existing duplicate values, this will fail.

*/
-- AlterTable
ALTER TABLE "User" ADD COLUMN     "emailChangeToken" TEXT,
ADD COLUMN     "emailChangeTokenExpiresAt" TIMESTAMP(3);

-- CreateIndex
CREATE UNIQUE INDEX "User_emailChangeToken_key" ON "User"("emailChangeToken");
