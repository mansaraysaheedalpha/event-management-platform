-- Grant platform admin access to a user
-- Replace 'YOUR_EMAIL@example.com' with the actual email address

-- First, check if the user exists
SELECT
  id,
  email,
  first_name,
  last_name,
  is_platform_admin
FROM users
WHERE email = 'YOUR_EMAIL@example.com';

-- If the user exists, grant admin access
UPDATE users
SET is_platform_admin = true
WHERE email = 'YOUR_EMAIL@example.com';

-- Verify the change
SELECT
  id,
  email,
  first_name,
  last_name,
  is_platform_admin,
  'Admin access granted! User must log out and log back in.' as note
FROM users
WHERE email = 'YOUR_EMAIL@example.com';
