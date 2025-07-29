-- CreateTable
CREATE TABLE "content_drop_logs" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "dropperId" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT,
    "contentType" TEXT NOT NULL,
    "contentUrl" TEXT NOT NULL,

    CONSTRAINT "content_drop_logs_pkey" PRIMARY KEY ("id")
);

-- AddForeignKey
ALTER TABLE "content_drop_logs" ADD CONSTRAINT "content_drop_logs_dropperId_fkey" FOREIGN KEY ("dropperId") REFERENCES "user_references"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "content_drop_logs" ADD CONSTRAINT "content_drop_logs_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "chat_sessions"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
