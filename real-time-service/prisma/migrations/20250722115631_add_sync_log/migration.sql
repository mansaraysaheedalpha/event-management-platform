-- CreateTable
CREATE TABLE "sync_logs" (
    "id" TEXT NOT NULL,
    "timestamp" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "userId" TEXT NOT NULL,
    "resource" TEXT NOT NULL,
    "action" TEXT NOT NULL,
    "payload" JSONB NOT NULL,

    CONSTRAINT "sync_logs_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "sync_logs_userId_timestamp_idx" ON "sync_logs"("userId", "timestamp");

-- AddForeignKey
ALTER TABLE "sync_logs" ADD CONSTRAINT "sync_logs_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user_references"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
