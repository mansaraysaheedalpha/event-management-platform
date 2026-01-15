-- CreateEnum
CREATE TYPE "HuddleStatus" AS ENUM ('FORMING', 'CONFIRMED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED');

-- CreateEnum
CREATE TYPE "HuddleType" AS ENUM ('PROBLEM_BASED', 'SESSION_BASED', 'PROXIMITY_BASED', 'MANUAL');

-- CreateEnum
CREATE TYPE "HuddleParticipantStatus" AS ENUM ('INVITED', 'ACCEPTED', 'DECLINED', 'ATTENDED', 'NO_SHOW');

-- CreateTable
CREATE TABLE "huddles" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "topic" VARCHAR(100) NOT NULL,
    "problemStatement" TEXT,
    "description" TEXT,
    "eventId" TEXT NOT NULL,
    "sessionId" TEXT,
    "locationName" VARCHAR(255),
    "locationDetails" TEXT,
    "scheduledAt" TIMESTAMP(3) NOT NULL,
    "duration" INTEGER NOT NULL DEFAULT 15,
    "status" "HuddleStatus" NOT NULL DEFAULT 'FORMING',
    "huddleType" "HuddleType" NOT NULL DEFAULT 'PROBLEM_BASED',
    "minParticipants" INTEGER NOT NULL DEFAULT 2,
    "maxParticipants" INTEGER NOT NULL DEFAULT 6,
    "version" INTEGER NOT NULL DEFAULT 1,
    "createdById" TEXT,

    CONSTRAINT "huddles_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "huddle_participants" (
    "id" TEXT NOT NULL,
    "huddleId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "status" "HuddleParticipantStatus" NOT NULL DEFAULT 'INVITED',
    "invitedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "respondedAt" TIMESTAMP(3),
    "attendedAt" TIMESTAMP(3),
    "matchScore" DOUBLE PRECISION,
    "matchReason" TEXT,

    CONSTRAINT "huddle_participants_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "huddles_eventId_idx" ON "huddles"("eventId");

-- CreateIndex
CREATE INDEX "huddles_status_idx" ON "huddles"("status");

-- CreateIndex
CREATE INDEX "huddles_scheduledAt_idx" ON "huddles"("scheduledAt");

-- CreateIndex
CREATE INDEX "huddle_participants_userId_idx" ON "huddle_participants"("userId");

-- CreateIndex
CREATE INDEX "huddle_participants_huddleId_status_idx" ON "huddle_participants"("huddleId", "status");

-- CreateIndex
CREATE UNIQUE INDEX "huddle_participants_huddleId_userId_key" ON "huddle_participants"("huddleId", "userId");

-- AddForeignKey
ALTER TABLE "huddle_participants" ADD CONSTRAINT "huddle_participants_huddleId_fkey" FOREIGN KEY ("huddleId") REFERENCES "huddles"("id") ON DELETE CASCADE ON UPDATE CASCADE;
