-- Add isPlatformAdmin field to users table
-- Run this manually if you can't run Prisma migrations

ALTER TABLE users
ADD COLUMN is_platform_admin BOOLEAN NOT NULL DEFAULT false;

-- Create an index for faster lookups
CREATE INDEX idx_users_is_platform_admin ON users(is_platform_admin) WHERE is_platform_admin = true;

-- Verify the column was added
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'users' AND column_name = 'is_platform_admin';

SELECT 'Platform admin field added successfully!' as status;
