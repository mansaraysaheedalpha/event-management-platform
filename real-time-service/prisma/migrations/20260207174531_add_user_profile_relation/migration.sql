-- AddForeignKey
ALTER TABLE "UserProfile" ADD CONSTRAINT "UserProfile_userId_fkey" FOREIGN KEY ("userId") REFERENCES "UserReference"("id") ON DELETE CASCADE ON UPDATE CASCADE;
