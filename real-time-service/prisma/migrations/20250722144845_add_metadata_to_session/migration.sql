/*
  Warnings:

  - Added the required column `eventId` to the `chat_sessions` table without a default value. This is not possible if the table is not empty.
  - Added the required column `organizationId` to the `chat_sessions` table without a default value. This is not possible if the table is not empty.

*/
-- AlterTable
ALTER TABLE "chat_sessions" ADD COLUMN     "eventId" TEXT NOT NULL,
ADD COLUMN     "organizationId" TEXT NOT NULL;
