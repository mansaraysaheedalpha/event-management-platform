-- Add new PointReason enum values
ALTER TYPE "PointReason" ADD VALUE IF NOT EXISTS 'TEAM_CREATED';
ALTER TYPE "PointReason" ADD VALUE IF NOT EXISTS 'TEAM_JOINED';
ALTER TYPE "PointReason" ADD VALUE IF NOT EXISTS 'SESSION_JOINED';

-- AlterTable
ALTER TABLE "gamification_point_entries" ADD COLUMN "actionCount" INTEGER NOT NULL DEFAULT 0;

-- Backfill actionCount from existing points data
-- For each entry, set actionCount = points / base_point_value
-- MESSAGE_SENT=1, MESSAGE_REACTED=2, QUESTION_ASKED=5, QUESTION_UPVOTED=2,
-- POLL_CREATED=10, POLL_VOTED=1, WAITLIST_JOINED=3, TEAM_CREATED=5, TEAM_JOINED=3, SESSION_JOINED=2
UPDATE "gamification_point_entries" SET "actionCount" = CASE
  WHEN reason = 'MESSAGE_SENT' THEN GREATEST(points / 1, 1)
  WHEN reason = 'MESSAGE_REACTED' THEN GREATEST(points / 2, 1)
  WHEN reason = 'QUESTION_ASKED' THEN GREATEST(points / 5, 1)
  WHEN reason = 'QUESTION_UPVOTED' THEN GREATEST(points / 2, 1)
  WHEN reason = 'POLL_CREATED' THEN GREATEST(points / 10, 1)
  WHEN reason = 'POLL_VOTED' THEN GREATEST(points / 1, 1)
  WHEN reason = 'WAITLIST_JOINED' THEN GREATEST(points / 3, 1)
  WHEN reason = 'TEAM_CREATED' THEN GREATEST(points / 5, 1)
  WHEN reason = 'TEAM_JOINED' THEN GREATEST(points / 3, 1)
  WHEN reason = 'SESSION_JOINED' THEN GREATEST(points / 2, 1)
  ELSE GREATEST(points, 1)
END
WHERE "actionCount" = 0 AND points > 0;
