-- CreateEnum
CREATE TYPE "AgentNotificationType" AS ENUM ('ANOMALY_DETECTED', 'INTERVENTION_EXECUTED');

-- CreateEnum
CREATE TYPE "AgentNotificationSeverity" AS ENUM ('CRITICAL', 'WARNING', 'INFO');

-- CreateTable
CREATE TABLE "agent_notifications" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "eventId" TEXT NOT NULL,
    "sessionId" TEXT,
    "type" "AgentNotificationType" NOT NULL,
    "severity" "AgentNotificationSeverity" NOT NULL DEFAULT 'INFO',
    "data" JSONB NOT NULL,

    CONSTRAINT "agent_notifications_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "agent_notification_reads" (
    "userId" TEXT NOT NULL,
    "notificationId" TEXT NOT NULL,
    "readAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "agent_notification_reads_pkey" PRIMARY KEY ("userId","notificationId")
);

-- CreateIndex
CREATE INDEX "agent_notifications_eventId_idx" ON "agent_notifications"("eventId");

-- CreateIndex
CREATE INDEX "agent_notifications_eventId_createdAt_idx" ON "agent_notifications"("eventId", "createdAt" DESC);

-- AddForeignKey
ALTER TABLE "agent_notification_reads" ADD CONSTRAINT "agent_notification_reads_notificationId_fkey" FOREIGN KEY ("notificationId") REFERENCES "agent_notifications"("id") ON DELETE CASCADE ON UPDATE CASCADE;
