-- CreateEnum for BoothQueueStatus
CREATE TYPE "BoothQueueStatus" AS ENUM ('WAITING', 'ADMITTED', 'ENTERED', 'LEFT', 'EXPIRED');

-- AlterTable expo_booths - add maxVisitors column
ALTER TABLE "expo_booths" ADD COLUMN "maxVisitors" INTEGER;

-- CreateTable booth_queue_entries
CREATE TABLE "booth_queue_entries" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "boothId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "userName" VARCHAR(200) NOT NULL,
    "eventId" TEXT NOT NULL,
    "position" INTEGER NOT NULL,
    "status" "BoothQueueStatus" NOT NULL DEFAULT 'WAITING',
    "admittedAt" TIMESTAMP(3),
    "enteredAt" TIMESTAMP(3),
    "leftAt" TIMESTAMP(3),
    "socketId" VARCHAR(100),

    CONSTRAINT "booth_queue_entries_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "booth_queue_entries_boothId_userId_key" ON "booth_queue_entries"("boothId", "userId");

-- CreateIndex
CREATE INDEX "booth_queue_entries_boothId_status_idx" ON "booth_queue_entries"("boothId", "status");

-- CreateIndex
CREATE INDEX "booth_queue_entries_boothId_position_idx" ON "booth_queue_entries"("boothId", "position");

-- CreateIndex
CREATE INDEX "booth_queue_entries_userId_idx" ON "booth_queue_entries"("userId");

-- CreateIndex
CREATE INDEX "booth_queue_entries_socketId_idx" ON "booth_queue_entries"("socketId");

-- AddForeignKey
ALTER TABLE "booth_queue_entries" ADD CONSTRAINT "booth_queue_entries_boothId_fkey" FOREIGN KEY ("boothId") REFERENCES "expo_booths"("id") ON DELETE CASCADE ON UPDATE CASCADE;
