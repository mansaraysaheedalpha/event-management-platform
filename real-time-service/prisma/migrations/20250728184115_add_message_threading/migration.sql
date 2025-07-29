-- AlterTable
ALTER TABLE "messages" ADD COLUMN     "replyingToMessageId" TEXT;

-- AddForeignKey
ALTER TABLE "messages" ADD CONSTRAINT "messages_replyingToMessageId_fkey" FOREIGN KEY ("replyingToMessageId") REFERENCES "messages"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
