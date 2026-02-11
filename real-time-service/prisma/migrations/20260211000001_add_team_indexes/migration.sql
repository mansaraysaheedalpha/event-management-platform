-- CreateIndex
CREATE INDEX "teams_sessionId_idx" ON "teams"("sessionId");

-- CreateIndex
CREATE INDEX "teams_creatorId_idx" ON "teams"("creatorId");

-- CreateIndex
CREATE INDEX "team_memberships_teamId_idx" ON "team_memberships"("teamId");
