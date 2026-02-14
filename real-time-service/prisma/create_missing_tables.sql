-- Create missing gamification tables
-- Run this in Render Shell: psql $DATABASE_URL -f prisma/create_missing_tables.sql
-- Or paste into Render Shell: psql $DATABASE_URL then paste the SQL

-- Enums (create if not exist)
DO $$ BEGIN
  CREATE TYPE "TriviaGameStatus" AS ENUM ('DRAFT', 'ACTIVE', 'COMPLETED');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE "TriviaQuestionStatus" AS ENUM ('PENDING', 'ACTIVE', 'REVEALED');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- team_messages
CREATE TABLE IF NOT EXISTS "team_messages" (
  "id" TEXT NOT NULL,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "teamId" TEXT NOT NULL,
  "authorId" TEXT NOT NULL,
  "text" TEXT NOT NULL,
  "metadata" JSONB,
  "reactions" JSONB DEFAULT '{}',
  CONSTRAINT "team_messages_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "team_messages_teamId_fkey" FOREIGN KEY ("teamId") REFERENCES "teams"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "team_messages_authorId_fkey" FOREIGN KEY ("authorId") REFERENCES "user_references"("id") ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS "team_messages_teamId_createdAt_idx" ON "team_messages"("teamId", "createdAt");

-- trivia_games
CREATE TABLE IF NOT EXISTS "trivia_games" (
  "id" TEXT NOT NULL,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "sessionId" TEXT NOT NULL,
  "name" VARCHAR(200) NOT NULL,
  "status" "TriviaGameStatus" NOT NULL DEFAULT 'DRAFT',
  "timePerQuestion" INTEGER NOT NULL DEFAULT 30,
  "pointsCorrect" INTEGER NOT NULL DEFAULT 10,
  "pointsSpeedBonus" INTEGER NOT NULL DEFAULT 5,
  "createdById" TEXT NOT NULL,
  CONSTRAINT "trivia_games_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "trivia_games_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "chat_sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "trivia_games_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "user_references"("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS "trivia_games_sessionId_idx" ON "trivia_games"("sessionId");
CREATE INDEX IF NOT EXISTS "trivia_games_status_idx" ON "trivia_games"("status");

-- trivia_questions
CREATE TABLE IF NOT EXISTS "trivia_questions" (
  "id" TEXT NOT NULL,
  "gameId" TEXT NOT NULL,
  "questionText" TEXT NOT NULL,
  "options" TEXT[] NOT NULL,
  "correctIndex" INTEGER NOT NULL,
  "orderIndex" INTEGER NOT NULL,
  "status" "TriviaQuestionStatus" NOT NULL DEFAULT 'PENDING',
  CONSTRAINT "trivia_questions_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "trivia_questions_gameId_fkey" FOREIGN KEY ("gameId") REFERENCES "trivia_games"("id") ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS "trivia_questions_gameId_orderIndex_idx" ON "trivia_questions"("gameId", "orderIndex");

-- trivia_answers
CREATE TABLE IF NOT EXISTS "trivia_answers" (
  "id" TEXT NOT NULL,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "questionId" TEXT NOT NULL,
  "teamId" TEXT NOT NULL,
  "submittedById" TEXT NOT NULL,
  "selectedIndex" INTEGER NOT NULL,
  "isCorrect" BOOLEAN NOT NULL,
  "responseTimeMs" INTEGER NOT NULL,
  CONSTRAINT "trivia_answers_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "trivia_answers_questionId_teamId_key" UNIQUE ("questionId", "teamId"),
  CONSTRAINT "trivia_answers_questionId_fkey" FOREIGN KEY ("questionId") REFERENCES "trivia_questions"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "trivia_answers_teamId_fkey" FOREIGN KEY ("teamId") REFERENCES "teams"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "trivia_answers_submittedById_fkey" FOREIGN KEY ("submittedById") REFERENCES "user_references"("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS "trivia_answers_questionId_idx" ON "trivia_answers"("questionId");
CREATE INDEX IF NOT EXISTS "trivia_answers_teamId_idx" ON "trivia_answers"("teamId");

-- trivia_team_scores
CREATE TABLE IF NOT EXISTS "trivia_team_scores" (
  "id" TEXT NOT NULL,
  "gameId" TEXT NOT NULL,
  "teamId" TEXT NOT NULL,
  "totalScore" INTEGER NOT NULL DEFAULT 0,
  "correctCount" INTEGER NOT NULL DEFAULT 0,
  "speedBonuses" INTEGER NOT NULL DEFAULT 0,
  CONSTRAINT "trivia_team_scores_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "trivia_team_scores_gameId_teamId_key" UNIQUE ("gameId", "teamId"),
  CONSTRAINT "trivia_team_scores_gameId_fkey" FOREIGN KEY ("gameId") REFERENCES "trivia_games"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "trivia_team_scores_teamId_fkey" FOREIGN KEY ("teamId") REFERENCES "teams"("id") ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS "trivia_team_scores_gameId_idx" ON "trivia_team_scores"("gameId");
