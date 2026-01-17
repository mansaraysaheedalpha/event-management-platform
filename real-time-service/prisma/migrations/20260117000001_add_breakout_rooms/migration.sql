-- CreateEnum
CREATE TYPE "BreakoutRoomStatus" AS ENUM ('WAITING', 'ACTIVE', 'CLOSING', 'CLOSED');

-- CreateEnum
CREATE TYPE "BreakoutParticipantRole" AS ENUM ('FACILITATOR', 'PARTICIPANT');

-- CreateTable
CREATE TABLE "breakout_rooms" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "sessionId" TEXT NOT NULL,
    "eventId" TEXT NOT NULL,
    "name" VARCHAR(100) NOT NULL,
    "topic" VARCHAR(500),
    "maxParticipants" INTEGER NOT NULL DEFAULT 8,
    "durationMinutes" INTEGER NOT NULL DEFAULT 15,
    "autoAssign" BOOLEAN NOT NULL DEFAULT false,
    "status" "BreakoutRoomStatus" NOT NULL DEFAULT 'WAITING',
    "startedAt" TIMESTAMP(3),
    "endedAt" TIMESTAMP(3),
    "creatorId" TEXT NOT NULL,
    "facilitatorId" TEXT,
    "videoRoomId" VARCHAR(255),
    "videoRoomUrl" VARCHAR(500),

    CONSTRAINT "breakout_rooms_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "breakout_participants" (
    "id" TEXT NOT NULL,
    "joinedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "leftAt" TIMESTAMP(3),
    "role" "BreakoutParticipantRole" NOT NULL DEFAULT 'PARTICIPANT',
    "speakingTimeSeconds" INTEGER NOT NULL DEFAULT 0,
    "userId" TEXT NOT NULL,
    "roomId" TEXT NOT NULL,

    CONSTRAINT "breakout_participants_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "breakout_rooms_sessionId_idx" ON "breakout_rooms"("sessionId");

-- CreateIndex
CREATE INDEX "breakout_rooms_eventId_idx" ON "breakout_rooms"("eventId");

-- CreateIndex
CREATE INDEX "breakout_rooms_status_idx" ON "breakout_rooms"("status");

-- CreateIndex
CREATE INDEX "breakout_participants_roomId_idx" ON "breakout_participants"("roomId");

-- CreateIndex
CREATE UNIQUE INDEX "breakout_participants_userId_roomId_key" ON "breakout_participants"("userId", "roomId");

-- AddForeignKey
ALTER TABLE "breakout_rooms" ADD CONSTRAINT "breakout_rooms_creatorId_fkey" FOREIGN KEY ("creatorId") REFERENCES "user_references"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "breakout_rooms" ADD CONSTRAINT "breakout_rooms_facilitatorId_fkey" FOREIGN KEY ("facilitatorId") REFERENCES "user_references"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "breakout_participants" ADD CONSTRAINT "breakout_participants_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user_references"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "breakout_participants" ADD CONSTRAINT "breakout_participants_roomId_fkey" FOREIGN KEY ("roomId") REFERENCES "breakout_rooms"("id") ON DELETE CASCADE ON UPDATE CASCADE;
