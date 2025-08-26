/*
  Warnings:

  - A unique constraint covering the columns `[restoreToken]` on the table `Organization` will be added. If there are existing duplicate values, this will fail.

*/
-- AlterTable
ALTER TABLE "public"."Organization" ADD COLUMN     "restoreToken" TEXT;

-- CreateIndex
CREATE UNIQUE INDEX "Organization_restoreToken_key" ON "public"."Organization"("restoreToken");
