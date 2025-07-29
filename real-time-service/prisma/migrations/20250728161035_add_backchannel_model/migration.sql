-- CreateTable
CREATE TABLE "backchannel_messages" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "text" TEXT NOT NULL,
    "senderId" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,

    CONSTRAINT "backchannel_messages_pkey" PRIMARY KEY ("id")
);

-- AddForeignKey
ALTER TABLE "backchannel_messages" ADD CONSTRAINT "backchannel_messages_senderId_fkey" FOREIGN KEY ("senderId") REFERENCES "user_references"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "backchannel_messages" ADD CONSTRAINT "backchannel_messages_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "chat_sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;
