-- CreateEnum
CREATE TYPE "GiveawayType" AS ENUM ('SINGLE_POLL', 'QUIZ_SCORE');

-- CreateEnum
CREATE TYPE "ClaimStatus" AS ENUM ('PENDING', 'CLAIMED', 'EXPIRED');

-- AlterTable
ALTER TABLE "polls" ADD COLUMN     "correctOptionId" TEXT,
ADD COLUMN     "giveawayEnabled" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "isQuiz" BOOLEAN NOT NULL DEFAULT false;

-- CreateTable
CREATE TABLE "giveaway_winners" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "sessionId" TEXT NOT NULL,
    "eventId" TEXT NOT NULL,
    "pollId" TEXT,
    "userId" TEXT NOT NULL,
    "winnerName" TEXT NOT NULL,
    "winnerEmail" TEXT NOT NULL,
    "giveawayType" "GiveawayType" NOT NULL,
    "winningOptionText" TEXT,
    "quizScore" INTEGER,
    "quizTotal" INTEGER,
    "prizeTitle" TEXT,
    "prizeDescription" TEXT,
    "prizeType" TEXT,
    "prizeValue" DECIMAL(10,2),
    "claimInstructions" TEXT,
    "claimLocation" TEXT,
    "claimDeadline" TIMESTAMP(3),
    "claimedAt" TIMESTAMP(3),
    "claimStatus" "ClaimStatus" NOT NULL DEFAULT 'PENDING',
    "emailSent" BOOLEAN NOT NULL DEFAULT false,
    "emailSentAt" TIMESTAMP(3),
    "notificationError" TEXT,
    "createdById" TEXT,

    CONSTRAINT "giveaway_winners_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "session_quiz_settings" (
    "id" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "quizEnabled" BOOLEAN NOT NULL DEFAULT false,
    "passingScore" INTEGER NOT NULL DEFAULT 3,
    "totalQuestions" INTEGER,
    "prizeTitle" TEXT,
    "prizeDescription" TEXT,
    "prizeType" TEXT DEFAULT 'virtual',
    "prizeValue" DECIMAL(10,2),
    "claimInstructions" TEXT,
    "claimLocation" TEXT,
    "claimDeadlineHours" INTEGER NOT NULL DEFAULT 72,
    "maxWinners" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "session_quiz_settings_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "giveaway_winners_sessionId_idx" ON "giveaway_winners"("sessionId");

-- CreateIndex
CREATE INDEX "giveaway_winners_eventId_idx" ON "giveaway_winners"("eventId");

-- CreateIndex
CREATE INDEX "giveaway_winners_userId_idx" ON "giveaway_winners"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "session_quiz_settings_sessionId_key" ON "session_quiz_settings"("sessionId");

-- AddForeignKey
ALTER TABLE "giveaway_winners" ADD CONSTRAINT "giveaway_winners_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "chat_sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "giveaway_winners" ADD CONSTRAINT "giveaway_winners_pollId_fkey" FOREIGN KEY ("pollId") REFERENCES "polls"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "session_quiz_settings" ADD CONSTRAINT "session_quiz_settings_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "chat_sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;
