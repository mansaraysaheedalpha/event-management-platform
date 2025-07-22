-- CreateTable
CREATE TABLE "presentations" (
    "id" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "slideUrls" TEXT[],

    CONSTRAINT "presentations_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "presentations_sessionId_key" ON "presentations"("sessionId");

-- AddForeignKey
ALTER TABLE "presentations" ADD CONSTRAINT "presentations_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "chat_sessions"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
