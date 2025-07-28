

-- CreateTable
CREATE TABLE "gamification_point_entries" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "points" INTEGER NOT NULL,
    "reason" TEXT NOT NULL CHECK ("reason" IN ('MESSAGE_SENT', 'QUESTION_ASKED', 'QUESTION_UPVOTED', 'POLL_VOTED')),
    "userId" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,


    CONSTRAINT "gamification_point_entries_pkey" PRIMARY KEY ("id")
);

-- Indexes for efficient queries
CREATE INDEX "gamification_point_entries_userId_idx" ON "gamification_point_entries"("userId");
CREATE INDEX "gamification_point_entries_sessionId_idx" ON "gamification_point_entries"("sessionId");
CREATE INDEX "gamification_point_entries_userId_createdAt_idx" ON "gamification_point_entries"("userId", "createdAt");

-- CreateTable
CREATE TABLE "gamification_achievements" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "badgeName" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "userId" TEXT NOT NULL,

    CONSTRAINT "gamification_achievements_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "gamification_achievements_userId_badgeName_key" ON "gamification_achievements"("userId", "badgeName");

-- AddForeignKey
ALTER TABLE "gamification_point_entries" ADD CONSTRAINT "gamification_point_entries_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user_references"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "gamification_point_entries" ADD CONSTRAINT "gamification_point_entries_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "chat_sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "gamification_achievements" ADD CONSTRAINT "gamification_achievements_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user_references"("id") ON DELETE CASCADE ON UPDATE CASCADE;
