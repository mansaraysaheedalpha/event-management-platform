-- CreateEnum
CREATE TYPE "ConnectionStrength" AS ENUM ('WEAK', 'MODERATE', 'STRONG');

-- CreateEnum
CREATE TYPE "ConnectionActivityType" AS ENUM ('INITIAL_CONNECT', 'DM_SENT', 'DM_RECEIVED', 'HUDDLE_TOGETHER', 'FOLLOW_UP_SENT', 'FOLLOW_UP_OPENED', 'FOLLOW_UP_REPLIED', 'MEETING_SCHEDULED', 'MEETING_HELD', 'OUTCOME_REPORTED', 'LINKEDIN_CONNECTED');

-- AlterTable
ALTER TABLE "connections" ADD COLUMN     "followUpMessage" TEXT,
ADD COLUMN     "interactionCount" INTEGER NOT NULL DEFAULT 1,
ADD COLUMN     "lastInteractionAt" TIMESTAMP(3),
ADD COLUMN     "strength" "ConnectionStrength" NOT NULL DEFAULT 'WEAK';

-- CreateTable
CREATE TABLE "connection_activities" (
    "id" TEXT NOT NULL,
    "connectionId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "activityType" "ConnectionActivityType" NOT NULL,
    "description" TEXT,
    "metadata" JSONB,
    "initiatorId" TEXT,

    CONSTRAINT "connection_activities_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "connection_activities_connectionId_idx" ON "connection_activities"("connectionId");

-- CreateIndex
CREATE INDEX "connection_activities_createdAt_idx" ON "connection_activities"("createdAt");

-- CreateIndex
CREATE INDEX "connection_activities_activityType_idx" ON "connection_activities"("activityType");

-- CreateIndex
CREATE INDEX "connections_strength_idx" ON "connections"("strength");

-- AddForeignKey
ALTER TABLE "connection_activities" ADD CONSTRAINT "connection_activities_connectionId_fkey" FOREIGN KEY ("connectionId") REFERENCES "connections"("id") ON DELETE CASCADE ON UPDATE CASCADE;
