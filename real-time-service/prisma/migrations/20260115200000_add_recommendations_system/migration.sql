-- CreateTable
CREATE TABLE "user_profiles" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "bio" TEXT,
    "industry" TEXT,
    "goals" TEXT[],
    "interests" TEXT[],
    "skillsToOffer" TEXT[],
    "skillsNeeded" TEXT[],
    "linkedInUrl" TEXT,
    "linkedInHeadline" TEXT,
    "linkedInSummary" TEXT,
    "linkedInExperience" JSONB,
    "linkedInEducation" JSONB,
    "linkedInSkills" TEXT[],
    "linkedInLastSync" TIMESTAMP(3),
    "githubUsername" TEXT,
    "githubBio" TEXT,
    "githubTopLanguages" TEXT[],
    "githubRepoCount" INTEGER,
    "githubLastSync" TIMESTAMP(3),
    "twitterHandle" TEXT,
    "extractedSkills" TEXT[],
    "profileCompleteness" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "user_profiles_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "recommendations" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "eventId" TEXT NOT NULL,
    "recommendedUserId" TEXT NOT NULL,
    "matchScore" INTEGER NOT NULL,
    "reasons" TEXT[],
    "conversationStarters" TEXT[],
    "potentialValue" TEXT,
    "generatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "viewed" BOOLEAN NOT NULL DEFAULT false,
    "viewedAt" TIMESTAMP(3),
    "pinged" BOOLEAN NOT NULL DEFAULT false,
    "pingedAt" TIMESTAMP(3),
    "connected" BOOLEAN NOT NULL DEFAULT false,
    "connectedAt" TIMESTAMP(3),

    CONSTRAINT "recommendations_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "connection_feedback" (
    "id" TEXT NOT NULL,
    "connectionId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "rating" INTEGER NOT NULL,
    "wasValuable" BOOLEAN,
    "willFollowUp" BOOLEAN,
    "wouldRecommend" BOOLEAN,
    "positiveFactors" TEXT[],
    "negativeFactors" TEXT[],
    "comments" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "connection_feedback_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "recommendation_feedback" (
    "id" TEXT NOT NULL,
    "recommendationId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "feedbackType" TEXT NOT NULL,
    "reason" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "recommendation_feedback_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "user_profiles_userId_key" ON "user_profiles"("userId");

-- CreateIndex
CREATE INDEX "user_profiles_userId_idx" ON "user_profiles"("userId");

-- CreateIndex
CREATE INDEX "recommendations_userId_eventId_idx" ON "recommendations"("userId", "eventId");

-- CreateIndex
CREATE INDEX "recommendations_eventId_expiresAt_idx" ON "recommendations"("eventId", "expiresAt");

-- CreateIndex
CREATE UNIQUE INDEX "recommendations_userId_eventId_recommendedUserId_key" ON "recommendations"("userId", "eventId", "recommendedUserId");

-- CreateIndex
CREATE INDEX "connection_feedback_connectionId_idx" ON "connection_feedback"("connectionId");

-- CreateIndex
CREATE UNIQUE INDEX "connection_feedback_connectionId_userId_key" ON "connection_feedback"("connectionId", "userId");

-- CreateIndex
CREATE INDEX "recommendation_feedback_recommendationId_idx" ON "recommendation_feedback"("recommendationId");

-- CreateIndex
CREATE UNIQUE INDEX "recommendation_feedback_recommendationId_userId_key" ON "recommendation_feedback"("recommendationId", "userId");
