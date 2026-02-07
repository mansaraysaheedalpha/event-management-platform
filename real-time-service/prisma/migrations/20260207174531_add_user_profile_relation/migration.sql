-- AddForeignKey
ALTER TABLE "user_profiles" ADD CONSTRAINT "user_profiles_userId_fkey" FOREIGN KEY ("userId") REFERENCES "UserReference"("id") ON DELETE CASCADE ON UPDATE CASCADE;
