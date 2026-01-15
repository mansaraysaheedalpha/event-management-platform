-- Add missing columns to user_profiles if they don't exist
-- This migration handles cases where the table was created without all columns

-- Create enums if they don't exist
DO $$ BEGIN
    CREATE TYPE "Goal" AS ENUM ('LEARN', 'NETWORK', 'HIRE', 'GET_HIRED', 'FIND_PARTNERS', 'FIND_INVESTORS', 'SELL', 'BUY', 'MENTOR', 'GET_MENTORED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE "CompanySize" AS ENUM ('SOLO', 'STARTUP_1_10', 'SMALL_11_50', 'MEDIUM_51_200', 'LARGE_201_1000', 'ENTERPRISE_1000_PLUS');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE "EnrichmentStatus" AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'OPTED_OUT');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Add missing columns to user_profiles
ALTER TABLE "user_profiles" ADD COLUMN IF NOT EXISTS "companySize" "CompanySize";
ALTER TABLE "user_profiles" ADD COLUMN IF NOT EXISTS "yearsExperience" INTEGER;
ALTER TABLE "user_profiles" ADD COLUMN IF NOT EXISTS "enrichmentStatus" "EnrichmentStatus" DEFAULT 'PENDING';
ALTER TABLE "user_profiles" ADD COLUMN IF NOT EXISTS "enrichedAt" TIMESTAMP(3);
ALTER TABLE "user_profiles" ADD COLUMN IF NOT EXISTS "twitterBio" TEXT;
ALTER TABLE "user_profiles" ADD COLUMN IF NOT EXISTS "youtubeChannelUrl" TEXT;
ALTER TABLE "user_profiles" ADD COLUMN IF NOT EXISTS "youtubeChannelName" TEXT;
ALTER TABLE "user_profiles" ADD COLUMN IF NOT EXISTS "youtubeSubscriberRange" TEXT;
ALTER TABLE "user_profiles" ADD COLUMN IF NOT EXISTS "instagramHandle" TEXT;
ALTER TABLE "user_profiles" ADD COLUMN IF NOT EXISTS "instagramBio" TEXT;
ALTER TABLE "user_profiles" ADD COLUMN IF NOT EXISTS "facebookProfileUrl" TEXT;
ALTER TABLE "user_profiles" ADD COLUMN IF NOT EXISTS "personalWebsite" TEXT;
ALTER TABLE "user_profiles" ADD COLUMN IF NOT EXISTS "extractedInterests" TEXT[];
ALTER TABLE "user_profiles" ADD COLUMN IF NOT EXISTS "enrichmentSources" TEXT[];

-- Update goals column to use Goal enum if it's currently TEXT[]
-- Note: This requires data migration if goals has existing data
DO $$
BEGIN
    -- Check if goals column is TEXT[] and needs conversion
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_profiles'
        AND column_name = 'goals'
        AND data_type = 'ARRAY'
        AND udt_name = '_text'
    ) THEN
        -- For empty tables or new setups, we can just alter the type
        -- For existing data, this would need careful migration
        -- Skipping type conversion to avoid data loss
        RAISE NOTICE 'Goals column exists as TEXT[], keeping as-is to preserve data';
    END IF;
END $$;
