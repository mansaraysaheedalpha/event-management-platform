-- CreateEnum
CREATE TYPE "ConnectionType" AS ENUM ('PROXIMITY_PING', 'DM_INITIATED', 'SESSION_QA', 'MANUAL_EXCHANGE');

-- CreateEnum
CREATE TYPE "OutcomeType" AS ENUM ('MEETING_HELD', 'JOB_REFERRAL', 'PARTNERSHIP', 'SALE_DEAL', 'MENTORSHIP', 'OTHER');

-- CreateEnum
CREATE TYPE "ContextType" AS ENUM ('SHARED_SESSION', 'SHARED_INTEREST', 'MUTUAL_CONNECTION', 'SAME_COMPANY_SIZE', 'SAME_INDUSTRY', 'QA_INTERACTION');

-- AlterTable
ALTER TABLE "user_references" ADD COLUMN "avatarUrl" TEXT;

-- CreateTable
CREATE TABLE "connections" (
    "id" TEXT NOT NULL,
    "userAId" TEXT NOT NULL,
    "userBId" TEXT NOT NULL,
    "eventId" TEXT NOT NULL,
    "connectedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "connectionType" "ConnectionType" NOT NULL DEFAULT 'PROXIMITY_PING',
    "initialMessage" TEXT,
    "followUpSentAt" TIMESTAMP(3),
    "followUpOpenedAt" TIMESTAMP(3),
    "followUpRepliedAt" TIMESTAMP(3),
    "meetingScheduled" BOOLEAN NOT NULL DEFAULT false,
    "meetingDate" TIMESTAMP(3),
    "outcomeType" "OutcomeType",
    "outcomeNotes" TEXT,
    "outcomeReportedAt" TIMESTAMP(3),

    CONSTRAINT "connections_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "connection_contexts" (
    "id" TEXT NOT NULL,
    "connectionId" TEXT NOT NULL,
    "contextType" "ContextType" NOT NULL,
    "contextValue" TEXT NOT NULL,

    CONSTRAINT "connection_contexts_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "connections_userAId_idx" ON "connections"("userAId");

-- CreateIndex
CREATE INDEX "connections_userBId_idx" ON "connections"("userBId");

-- CreateIndex
CREATE INDEX "connections_eventId_idx" ON "connections"("eventId");

-- CreateIndex
CREATE UNIQUE INDEX "connections_userAId_userBId_eventId_key" ON "connections"("userAId", "userBId", "eventId");

-- CreateIndex
CREATE INDEX "connection_contexts_connectionId_idx" ON "connection_contexts"("connectionId");

-- AddForeignKey
ALTER TABLE "connections" ADD CONSTRAINT "connections_userAId_fkey" FOREIGN KEY ("userAId") REFERENCES "user_references"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "connections" ADD CONSTRAINT "connections_userBId_fkey" FOREIGN KEY ("userBId") REFERENCES "user_references"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "connection_contexts" ADD CONSTRAINT "connection_contexts_connectionId_fkey" FOREIGN KEY ("connectionId") REFERENCES "connections"("id") ON DELETE CASCADE ON UPDATE CASCADE;
