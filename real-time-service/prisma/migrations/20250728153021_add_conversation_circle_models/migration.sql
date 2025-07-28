/*
  Warnings:

  - The primary key for the `message_reactions` table will be changed. If it partially fails, the table could be left without primary key constraint.
  - You are about to drop the column `isAnswered` on the `questions` table. All the data in the column will be lost.
  - A unique constraint covering the columns `[userId,sessionId,reason]` on the table `gamification_point_entries` will be added. If there are existing duplicate values, this will fail.
  - A unique constraint covering the columns `[userId,messageId,emoji]` on the table `message_reactions` will be added. If there are existing duplicate values, this will fail.
  - Changed the type of `reason` on the `gamification_point_entries` table. No cast exists, the column would be dropped and recreated, which cannot be done if there is data, since the column is required.
  - The required column `id` was added to the `message_reactions` table with a prisma-level default value. This is not possible if the table is not empty. Please add this column as optional, then populate it before making it required.

*/
-- CreateEnum
CREATE TYPE "PointReason" AS ENUM ('MESSAGE_SENT', 'MESSAGE_REACTED', 'QUESTION_ASKED', 'QUESTION_UPVOTED', 'POLL_CREATED', 'POLL_VOTED', 'WAITLIST_JOINED');

-- DropForeignKey
ALTER TABLE "answers" DROP CONSTRAINT "answers_authorId_fkey";

-- DropIndex
DROP INDEX "gamification_point_entries_sessionId_idx";

-- DropIndex
DROP INDEX "gamification_point_entries_userId_createdAt_idx";

-- DropIndex
DROP INDEX "gamification_point_entries_userId_idx";

-- DropIndex
DROP INDEX "message_reactions_messageId_idx";

-- AlterTable
ALTER TABLE "answers" ALTER COLUMN "id" DROP DEFAULT;

-- AlterTable
ALTER TABLE "gamification_point_entries" DROP COLUMN "reason",
ADD COLUMN     "reason" "PointReason" NOT NULL;

-- AlterTable
ALTER TABLE "message_reactions" DROP CONSTRAINT "message_reactions_pkey",
ADD COLUMN     "id" TEXT NOT NULL,
ADD CONSTRAINT "message_reactions_pkey" PRIMARY KEY ("id");

-- AlterTable
ALTER TABLE "questions" DROP COLUMN "isAnswered";

-- CreateTable
CREATE TABLE "conversation_circles" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "topic" VARCHAR(255) NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "creatorId" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,

    CONSTRAINT "conversation_circles_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "conversation_circle_participants" (
    "joinedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "userId" TEXT NOT NULL,
    "circleId" TEXT NOT NULL,

    CONSTRAINT "conversation_circle_participants_pkey" PRIMARY KEY ("userId","circleId")
);

-- CreateIndex
CREATE INDEX "gamification_point_entries_userId_sessionId_idx" ON "gamification_point_entries"("userId", "sessionId");

-- CreateIndex
CREATE UNIQUE INDEX "gamification_point_entries_userId_sessionId_reason_key" ON "gamification_point_entries"("userId", "sessionId", "reason");

-- CreateIndex
CREATE UNIQUE INDEX "message_reactions_userId_messageId_emoji_key" ON "message_reactions"("userId", "messageId", "emoji");

-- AddForeignKey
ALTER TABLE "answers" ADD CONSTRAINT "answers_authorId_fkey" FOREIGN KEY ("authorId") REFERENCES "user_references"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "conversation_circles" ADD CONSTRAINT "conversation_circles_creatorId_fkey" FOREIGN KEY ("creatorId") REFERENCES "user_references"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "conversation_circles" ADD CONSTRAINT "conversation_circles_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "chat_sessions"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "conversation_circle_participants" ADD CONSTRAINT "conversation_circle_participants_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user_references"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "conversation_circle_participants" ADD CONSTRAINT "conversation_circle_participants_circleId_fkey" FOREIGN KEY ("circleId") REFERENCES "conversation_circles"("id") ON DELETE CASCADE ON UPDATE CASCADE;
